# Hybrid NumPy/PyArrow Computation Design for Interaction Terms

## Overview
This design leverages NumPy for mathematical computations and PyArrow for efficient data I/O, checkpointing, and inter-process communication.

## Architecture Components

### 1. Data Flow Pipeline
```
SQLite DB → PyArrow Batch Reader → NumPy Computation → PyArrow Buffer → SQLite Batch Writer
                                          ↓
                                  PyArrow Checkpoint Files
```

### 2. Memory Management Strategy
- **Working memory**: 4-6GB for active computation
- **PyArrow buffers**: 2GB for I/O operations  
- **Checkpoint storage**: Temporary Parquet files (~500MB each)
- **Total footprint**: ~8GB peak usage

## Detailed Implementation

### Core Classes

#### 1. BatchDataLoader (PyArrow-based)
```python
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np
from typing import Iterator, Dict, List, Tuple

class BatchDataLoader:
    def __init__(self, db_path: str, batch_size: int = 10000):
        self.db_path = db_path
        self.batch_size = batch_size
        self.schema = pa.schema([
            ('rider_result_id', pa.int64()),
            ('competition_id', pa.int64()),
            ('rider_id', pa.int64()),
            ('correlation_type', pa.string()),
            ('percentile', pa.int32()),
            ('correlation_values', pa.list_(pa.float64())),
            ('race_feature_values', pa.list_(pa.float64()))
        ])
    
    def load_correlations_batch(self, 
                               competition_ids: List[int]) -> pa.Table:
        """Load correlations using PyArrow for efficient batching"""
        # Query correlations
        query = """
        SELECT 
            rd.rider_result_id,
            rd.competition_id,
            rd.rider_id,
            rd.correlation_type,
            rd.percentile,
            GROUP_CONCAT(rd.correlation_value) as correlation_values
        FROM rider_correlations_denorm rd
        WHERE rd.competition_id IN ({})
        GROUP BY rd.rider_result_id, rd.correlation_type, rd.percentile
        """.format(','.join('?' * len(competition_ids)))
        
        # Execute and convert to Arrow table
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql(query, conn, params=competition_ids)
            
        # Parse concatenated values into arrays
        df['correlation_values'] = df['correlation_values'].apply(
            lambda x: np.fromstring(x, sep=',') if x else np.full(37, np.nan)
        )
        
        return pa.Table.from_pandas(df, schema=self.schema)
    
    def load_race_features_batch(self, 
                                competition_ids: List[int],
                                percentiles: List[int]) -> Dict[Tuple[int, int], np.ndarray]:
        """Load race features into memory-efficient dictionary"""
        features = {}
        
        for percentile in percentiles:
            table_name = f"race_feature_{percentile}"
            query = f"""
            SELECT competition_id, * FROM {table_name}
            WHERE competition_id IN ({','.join('?' * len(competition_ids))})
            """
            
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql(query, conn, params=competition_ids)
                
            # Convert to NumPy arrays
            for _, row in df.iterrows():
                comp_id = row['competition_id']
                # Extract feature columns (excluding metadata)
                feature_values = row[RACE_FEATURES].values.astype(np.float64)
                features[(comp_id, percentile)] = feature_values
                
        return features
```

#### 2. InteractionComputer (NumPy-based)
```python
class InteractionComputer:
    def __init__(self):
        self.feature_names = RACE_FEATURES  # List of 37 feature names
        
    def compute_interactions(self, 
                           correlation_vec: np.ndarray,
                           feature_vec: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Compute all three interaction types using NumPy.
        
        Args:
            correlation_vec: Shape (37,) - rider's correlation values
            feature_vec: Shape (37,) - race feature values
            
        Returns:
            Dictionary with 'dot_product', 'cosine_similarity', 'hadamard'
        """
        # Handle NaN values
        mask = ~(np.isnan(correlation_vec) | np.isnan(feature_vec))
        
        if np.sum(mask) == 0:
            return {
                'dot_product': np.nan,
                'cosine_similarity': np.nan,
                'hadamard': np.full(37, np.nan)
            }
        
        # Masked vectors for valid computations
        corr_masked = correlation_vec[mask]
        feat_masked = feature_vec[mask]
        
        # Dot product
        dot_product = np.dot(corr_masked, feat_masked)
        
        # Cosine similarity
        corr_norm = np.linalg.norm(corr_masked)
        feat_norm = np.linalg.norm(feat_masked)
        
        if corr_norm > 0 and feat_norm > 0:
            cosine_similarity = dot_product / (corr_norm * feat_norm)
        else:
            cosine_similarity = 0.0
            
        # Hadamard product (element-wise)
        hadamard = correlation_vec * feature_vec
        
        return {
            'dot_product': dot_product,
            'cosine_similarity': cosine_similarity,
            'hadamard': hadamard
        }
    
    def compute_batch_vectorized(self,
                                correlations: np.ndarray,
                                features: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Vectorized computation for multiple riders at once.
        
        Args:
            correlations: Shape (n_riders, 37)
            features: Shape (n_riders, 37) or (37,) for same features
            
        Returns:
            Dictionary with arrays of results
        """
        # Ensure features has correct shape
        if features.ndim == 1:
            features = np.tile(features, (correlations.shape[0], 1))
            
        # Mask for valid values
        mask = ~(np.isnan(correlations) | np.isnan(features))
        
        # Vectorized dot products
        dots = np.sum(correlations * features * mask, axis=1)
        
        # Vectorized norms
        corr_norms = np.linalg.norm(correlations * mask, axis=1)
        feat_norms = np.linalg.norm(features * mask, axis=1)
        
        # Avoid division by zero
        norm_products = corr_norms * feat_norms
        norm_products[norm_products == 0] = 1.0
        
        # Cosine similarities
        cosines = dots / norm_products
        cosines[norm_products == 0] = 0.0
        
        # Hadamard products
        hadamards = correlations * features
        
        return {
            'dot_product': dots,
            'cosine_similarity': cosines,
            'hadamard': hadamards
        }
```

#### 3. CheckpointManager (PyArrow-based)
```python
class CheckpointManager:
    def __init__(self, checkpoint_dir: str = './checkpoints'):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        
    def save_checkpoint(self, 
                       data: Dict[str, np.ndarray],
                       metadata: Dict,
                       checkpoint_id: str):
        """Save computation state using PyArrow Parquet format"""
        # Flatten arrays for storage
        tables = []
        
        # Scalar interactions
        scalar_data = {
            'rider_result_id': data['rider_result_ids'],
            'correlation_type': data['correlation_types'],
            'percentile': data['percentiles'],
            'dot_product': data['dot_products'],
            'cosine_similarity': data['cosine_similarities']
        }
        scalar_table = pa.Table.from_pydict(scalar_data)
        
        # Hadamard interactions (flattened)
        hadamard_flat = data['hadamards'].reshape(-1)
        hadamard_data = {
            'rider_result_id': np.repeat(data['rider_result_ids'], 37),
            'correlation_type': np.repeat(data['correlation_types'], 37),
            'percentile': np.repeat(data['percentiles'], 37),
            'feature_idx': np.tile(np.arange(37), len(data['rider_result_ids'])),
            'interaction_value': hadamard_flat
        }
        hadamard_table = pa.Table.from_pydict(hadamard_data)
        
        # Write to Parquet files
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}"
        checkpoint_path.mkdir(exist_ok=True)
        
        pq.write_table(scalar_table, checkpoint_path / 'scalar.parquet',
                      compression='snappy')
        pq.write_table(hadamard_table, checkpoint_path / 'hadamard.parquet',
                      compression='snappy')
        
        # Save metadata
        with open(checkpoint_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f)
            
    def load_checkpoint(self, checkpoint_id: str) -> Tuple[Dict, Dict]:
        """Load checkpoint data efficiently"""
        checkpoint_path = self.checkpoint_dir / checkpoint_id
        
        # Load tables
        scalar_table = pq.read_table(checkpoint_path / 'scalar.parquet')
        hadamard_table = pq.read_table(checkpoint_path / 'hadamard.parquet')
        
        # Load metadata
        with open(checkpoint_path / 'metadata.json', 'r') as f:
            metadata = json.load(f)
            
        # Convert to numpy arrays
        data = {
            'scalar': scalar_table.to_pandas(),
            'hadamard': hadamard_table.to_pandas()
        }
        
        return data, metadata
```

#### 4. BatchResultWriter (Hybrid approach)
```python
class BatchResultWriter:
    def __init__(self, db_path: str, batch_size: int = 50000):
        self.db_path = db_path
        self.batch_size = batch_size
        self.scalar_buffer = []
        self.hadamard_buffer = []
        
    def add_results(self, results: Dict):
        """Add results to buffer"""
        # Process scalar results
        for i in range(len(results['rider_result_ids'])):
            self.scalar_buffer.extend([
                (results['rider_result_ids'][i],
                 results['competition_ids'][i],
                 results['rider_ids'][i],
                 results['correlation_types'][i],
                 results['percentiles'][i],
                 'dot_product',
                 results['dot_products'][i]),
                (results['rider_result_ids'][i],
                 results['competition_ids'][i],
                 results['rider_ids'][i],
                 results['correlation_types'][i],
                 results['percentiles'][i],
                 'cosine_similarity',
                 results['cosine_similarities'][i])
            ])
            
        # Process Hadamard results
        for i in range(len(results['rider_result_ids'])):
            for j, feature_name in enumerate(RACE_FEATURES):
                self.hadamard_buffer.append(
                    (results['rider_result_ids'][i],
                     results['competition_ids'][i],
                     results['rider_ids'][i],
                     results['correlation_types'][i],
                     results['percentiles'][i],
                     j,
                     feature_name,
                     results['hadamards'][i, j])
                )
                
        # Flush if buffer is full
        if len(self.scalar_buffer) >= self.batch_size:
            self.flush()
            
    def flush(self):
        """Write buffers to database"""
        if not self.scalar_buffer and not self.hadamard_buffer:
            return
            
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")
            
            # Batch insert scalar interactions
            if self.scalar_buffer:
                conn.executemany("""
                    INSERT OR IGNORE INTO rider_interactions_scalar
                    (rider_result_id, competition_id, rider_id, 
                     correlation_type, percentile, interaction_type, interaction_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, self.scalar_buffer)
                
            # Batch insert Hadamard interactions
            if self.hadamard_buffer:
                conn.executemany("""
                    INSERT OR IGNORE INTO rider_interactions_hadamard
                    (rider_result_id, competition_id, rider_id,
                     correlation_type, percentile, feature_idx, feature_name, interaction_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, self.hadamard_buffer)
                
            conn.commit()
            
        # Clear buffers
        self.scalar_buffer = []
        self.hadamard_buffer = []
```

### 5. Main Processing Pipeline
```python
class InteractionPipeline:
    def __init__(self, db_path: str, n_workers: int = 6):
        self.db_path = db_path
        self.n_workers = n_workers
        self.loader = BatchDataLoader(db_path)
        self.computer = InteractionComputer()
        self.writer = BatchResultWriter(db_path)
        self.checkpoint_mgr = CheckpointManager()
        
    def process_competition_batch(self, competition_ids: List[int]):
        """Process a batch of competitions"""
        # Load all race features for these competitions
        percentiles = [30, 40, 50, 60, 70, 80, 90, 100]
        race_features = self.loader.load_race_features_batch(
            competition_ids, percentiles
        )
        
        # Load correlations using PyArrow
        correlations_table = self.loader.load_correlations_batch(competition_ids)
        
        # Group by rider_result_id for efficient processing
        grouped = correlations_table.to_pandas().groupby(
            ['rider_result_id', 'correlation_type', 'percentile']
        )
        
        # Process each group
        results_buffer = {
            'rider_result_ids': [],
            'competition_ids': [],
            'rider_ids': [],
            'correlation_types': [],
            'percentiles': [],
            'dot_products': [],
            'cosine_similarities': [],
            'hadamards': []
        }
        
        for (rr_id, corr_type, percentile), group in grouped:
            comp_id = group.iloc[0]['competition_id']
            rider_id = group.iloc[0]['rider_id']
            
            # Get correlation vector
            corr_values = group.iloc[0]['correlation_values']
            
            # Get race feature vector
            feature_key = (comp_id, percentile)
            if feature_key not in race_features:
                continue  # Skip if race features missing
                
            feat_values = race_features[feature_key]
            
            # Compute interactions
            interactions = self.computer.compute_interactions(
                corr_values, feat_values
            )
            
            # Add to results buffer
            results_buffer['rider_result_ids'].append(rr_id)
            results_buffer['competition_ids'].append(comp_id)
            results_buffer['rider_ids'].append(rider_id)
            results_buffer['correlation_types'].append(corr_type)
            results_buffer['percentiles'].append(percentile)
            results_buffer['dot_products'].append(interactions['dot_product'])
            results_buffer['cosine_similarities'].append(interactions['cosine_similarity'])
            results_buffer['hadamards'].append(interactions['hadamard'])
            
        # Convert lists to numpy arrays for batch writing
        for key in ['dot_products', 'cosine_similarities']:
            results_buffer[key] = np.array(results_buffer[key])
        results_buffer['hadamards'] = np.array(results_buffer['hadamards'])
        
        # Write results
        self.writer.add_results(results_buffer)
        
        return len(results_buffer['rider_result_ids'])
    
    def run(self):
        """Main processing loop with checkpointing"""
        # Get all competitions to process
        with sqlite3.connect(self.db_path) as conn:
            competitions = pd.read_sql("""
                SELECT DISTINCT c.id 
                FROM competitions c
                WHERE EXISTS (
                    SELECT 1 FROM rider_correlations_denorm rd 
                    WHERE rd.competition_id = c.id
                )
                ORDER BY c.id
            """, conn)['id'].tolist()
            
        # Process in batches
        batch_size = 100
        total_processed = 0
        
        for i in range(0, len(competitions), batch_size):
            batch = competitions[i:i+batch_size]
            
            try:
                processed = self.process_competition_batch(batch)
                total_processed += processed
                
                # Checkpoint every 10 batches
                if (i // batch_size) % 10 == 0:
                    self.writer.flush()
                    self.checkpoint_mgr.save_checkpoint(
                        {'last_competition': batch[-1]},
                        {'total_processed': total_processed},
                        f"checkpoint_{i}"
                    )
                    
            except Exception as e:
                print(f"Error processing batch {i}: {e}")
                self.writer.flush()
                raise
                
        # Final flush
        self.writer.flush()
```

## Performance Optimizations

### 1. Memory-Mapped Files
```python
# For very large checkpoints, use memory mapping
memory_map = pa.memory_map('checkpoint.arrow')
with pa.ipc.open_file(memory_map) as reader:
    batch = reader.get_batch(0)
```

### 2. Zero-Copy Operations
```python
# Use Arrow's zero-copy conversion where possible
arrow_array = pa.array(numpy_array, type=pa.float64())
numpy_view = arrow_array.to_numpy(zero_copy_only=True)
```

### 3. Parallel Processing with Shared Memory
```python
# Use Arrow Plasma store for shared memory between processes
from pyarrow import plasma

# Start Plasma store (in separate process)
# plasma_store -m 1000000000 -s /tmp/plasma

# In workers
client = plasma.connect("/tmp/plasma")
object_id = client.put(large_array)

# In other workers
array = client.get(object_id)
```

## Expected Performance
- **Processing rate**: 200-300 rider results/second
- **Memory usage**: 6-8GB steady state
- **Checkpoint size**: ~100MB per 50k results
- **Total time**: 2-3 hours for complete dataset
- **I/O efficiency**: 90%+ time spent on computation vs I/O