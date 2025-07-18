# Feature Analysis Reporter Design

## Overview
A comprehensive reporting system that transforms feature analysis data into human-readable and LLM-consumable reports with multiple output formats.

## Report Architecture

### 1. Report Generator Framework

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import json
import markdown
from jinja2 import Template
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

class ReportSection(ABC):
    """Base class for report sections"""
    
    @abstractmethod
    def generate_content(self, data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def generate_summary(self, data: Dict[str, Any]) -> str:
        pass
    
    @abstractmethod
    def get_key_insights(self, data: Dict[str, Any]) -> List[str]:
        pass

class FeatureAnalysisReporter:
    def __init__(self, analysis_results: Dict[str, Any]):
        self.results = analysis_results
        self.timestamp = datetime.now()
        self.sections = self._initialize_sections()
        
    def _initialize_sections(self) -> List[ReportSection]:
        return [
            ExecutiveSummarySection(),
            FeatureBehaviorSection(),
            DistinctivenessAnalysisSection(),
            QualityMetricsSection(),
            FeatureGroupingSection(),
            RecommendationsSection(),
            TechnicalAppendixSection()
        ]
    
    def generate_report(self, format: str = 'markdown') -> str:
        """Generate report in specified format"""
        if format == 'markdown':
            return self._generate_markdown_report()
        elif format == 'html':
            return self._generate_html_report()
        elif format == 'json':
            return self._generate_json_report()
        elif format == 'llm_optimized':
            return self._generate_llm_optimized_report()
        else:
            raise ValueError(f"Unsupported format: {format}")
```

### 2. Report Sections

#### 2.1 Executive Summary Section
```python
class ExecutiveSummarySection(ReportSection):
    def generate_content(self, data: Dict[str, Any]) -> str:
        template = Template("""
# Executive Summary

## Analysis Overview
- **Total Features Analyzed**: {{ total_features }}
- **N Levels Examined**: {{ n_levels|join(', ') }}
- **Analysis Date**: {{ date }}

## Key Findings

### 1. Feature Stability
{{ feature_stability_summary }}

### 2. Optimal N-Level Combinations
{{ n_level_recommendations }}

### 3. Feature Quality Distribution
- **Tier 1 (Highest Quality)**: {{ tier1_count }} features
- **Tier 2 (Good Quality)**: {{ tier2_count }} features  
- **Tier 3 (Moderate Quality)**: {{ tier3_count }} features
- **Tier 4 (Low Quality)**: {{ tier4_count }} features

## Top Recommendations
{{ top_recommendations }}
        """)
        
        return template.render(
            total_features=len(data['feature_analysis']),
            n_levels=data['n_levels'],
            date=self.timestamp.strftime("%Y-%m-%d"),
            feature_stability_summary=self._summarize_stability(data),
            n_level_recommendations=self._summarize_n_recommendations(data),
            tier1_count=self._count_tier(data, 1),
            tier2_count=self._count_tier(data, 2),
            tier3_count=self._count_tier(data, 3),
            tier4_count=self._count_tier(data, 4),
            top_recommendations=self._get_top_recommendations(data)
        )
    
    def _summarize_stability(self, data: Dict[str, Any]) -> str:
        stable_features = [f for f, d in data['feature_analysis'].items() 
                          if d.get('stability_score', 0) > 0.8]
        
        return f"""
- **Highly Stable Features**: {len(stable_features)} features maintain consistent behavior across all N levels
- **Most Stable**: {', '.join(stable_features[:5])}
- **Stability Insight**: {self._get_stability_insight(data)}
        """
```

#### 2.2 Feature Behavior Section
```python
class FeatureBehaviorSection(ReportSection):
    def generate_content(self, data: Dict[str, Any]) -> str:
        content = ["# Feature Behavior Analysis\n"]
        
        # Group features by behavior pattern
        patterns = self._group_by_pattern(data)
        
        for pattern, features in patterns.items():
            content.append(f"## {pattern.title()} Features ({len(features)})\n")
            content.append(self._describe_pattern(pattern))
            
            # Table of features
            content.append("\n| Feature | Peak N | Reliability | Key Characteristic |")
            content.append("|---------|--------|-------------|-------------------|")
            
            for feature in features[:10]:  # Top 10 for each pattern
                feat_data = data['feature_analysis'][feature]
                content.append(f"| {feature} | {feat_data.get('distinctiveness', {}).get('peak_n', 'N/A')} | "
                             f"{feat_data.get('reliability', {}).get('overall_reliability', 0):.2f} | "
                             f"{self._get_key_characteristic(feat_data)} |")
            
            if len(features) > 10:
                content.append(f"\n*... and {len(features) - 10} more features*\n")
        
        return "\n".join(content)
    
    def _describe_pattern(self, pattern: str) -> str:
        descriptions = {
            'stable': "These features maintain consistent statistical properties across all N levels, making them reliable for analysis regardless of the rider subset.",
            'dilution': "These features show increasing variance as N increases, suggesting they capture elite-specific patterns that get diluted when including more riders.",
            'concentration': "These features become more concentrated (lower variance) as N increases, indicating convergence toward population norms.",
            'threshold': "These features exhibit sudden changes at specific N values, suggesting natural breakpoints in the rider population.",
            'bimodal': "These features show changing distribution shapes across N levels, often indicating multiple rider strategies or types."
        }
        return descriptions.get(pattern, "Features with this behavior pattern.")
```

#### 2.3 Visual Report Components
```python
class VisualReportGenerator:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        
    def generate_feature_behavior_heatmap(self) -> str:
        """Generate heatmap showing feature behavior across N levels"""
        # Create matrix of feature statistics across N
        features = list(self.data['feature_analysis'].keys())
        n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        
        # Create matrix for different metrics
        cv_matrix = []
        distinctiveness_matrix = []
        
        for feature in features:
            cv_row = []
            dist_row = []
            for n in n_levels:
                feat_data = self.data['feature_analysis'][feature]
                cv_value = feat_data.get('variability_analysis', {}).get(n, {}).get('cv', 0)
                dist_value = feat_data.get('distinctiveness', {}).get('trajectory', {}).get(n, {}).get('overall_distinctiveness', 0)
                
                cv_row.append(cv_value)
                dist_row.append(dist_value)
            
            cv_matrix.append(cv_row)
            distinctiveness_matrix.append(dist_row)
        
        # Create plotly heatmap
        fig = go.Figure()
        
        fig.add_trace(go.Heatmap(
            z=cv_matrix,
            x=[f'N={n}' for n in n_levels],
            y=features,
            colorscale='RdBu',
            name='Coefficient of Variation'
        ))
        
        fig.update_layout(
            title="Feature Coefficient of Variation Across N Levels",
            xaxis_title="N Level (% of riders included)",
            yaxis_title="Race Features",
            height=800
        )
        
        # Convert to HTML
        return fig.to_html(include_plotlyjs='cdn')
    
    def generate_feature_quality_scatter(self) -> str:
        """Generate scatter plot of feature quality metrics"""
        features = []
        reliability_scores = []
        distinctiveness_scores = []
        quality_tiers = []
        
        for feature, data in self.data['feature_analysis'].items():
            features.append(feature)
            reliability_scores.append(data.get('reliability', {}).get('overall_reliability', 0))
            distinctiveness_scores.append(
                max(data.get('distinctiveness', {}).get('trajectory', {}).values(), 
                    key=lambda x: x.get('overall_distinctiveness', 0)).get('overall_distinctiveness', 0)
            )
            quality_tiers.append(data.get('quality_tier', 4))
        
        fig = px.scatter(
            x=reliability_scores,
            y=distinctiveness_scores,
            text=features,
            color=quality_tiers,
            color_continuous_scale='Viridis',
            labels={
                'x': 'Reliability Score',
                'y': 'Peak Distinctiveness Score',
                'color': 'Quality Tier'
            },
            title='Feature Quality Analysis'
        )
        
        fig.update_traces(textposition='top center', textfont_size=8)
        
        return fig.to_html(include_plotlyjs='cdn')
```

#### 2.4 LLM-Optimized Report Format
```python
class LLMOptimizedReporter:
    def generate_llm_report(self, data: Dict[str, Any]) -> str:
        """Generate a structured report optimized for LLM consumption"""
        
        report = {
            "metadata": {
                "analysis_type": "race_feature_N_spectrum_analysis",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            },
            
            "summary": {
                "total_features": len(data['feature_analysis']),
                "n_levels_analyzed": [30, 40, 50, 60, 70, 80, 90, 100],
                "key_findings": self._extract_key_findings(data)
            },
            
            "feature_classifications": {
                "high_value_stable": self._get_features_by_criteria(
                    data, lambda f: f['stability_score'] > 0.8 and f['quality_tier'] <= 2
                ),
                "n_specific_valuable": self._get_n_specific_features(data),
                "redundant_pairs": self._get_redundant_pairs(data),
                "behavior_groups": data.get('feature_groups', {}).get('behavior_groups', {})
            },
            
            "recommendations": {
                "feature_selection": {
                    "minimal_set": self._get_minimal_feature_set(data),
                    "optimal_set": self._get_optimal_feature_set(data),
                    "n_level_combinations": data.get('n_recommendations', {})
                },
                
                "implementation_priority": [
                    {
                        "action": "Remove redundant features",
                        "features": self._get_redundant_features(data),
                        "expected_impact": "Reduce feature space by 15-20% with <1% information loss"
                    },
                    {
                        "action": "Focus on optimal N levels",
                        "n_levels": data.get('n_recommendations', {}).get('balanced_set', []),
                        "expected_impact": "Capture 95% of information with 50% fewer features"
                    }
                ]
            },
            
            "detailed_analysis": {
                feature: {
                    "behavior_pattern": analysis.get('behavior_pattern', {}).get('primary_pattern'),
                    "optimal_n_range": self._get_optimal_n_range(analysis),
                    "quality_metrics": {
                        "reliability": analysis.get('reliability', {}).get('overall_reliability', 0),
                        "peak_distinctiveness": self._get_peak_distinctiveness(analysis),
                        "stability_score": analysis.get('stability_score', 0)
                    },
                    "redundancy_info": self._get_redundancy_info(feature, data),
                    "recommendation": self._get_feature_recommendation(feature, analysis)
                }
                for feature, analysis in data['feature_analysis'].items()
            }
        }
        
        return json.dumps(report, indent=2)
```

#### 2.5 Human-Readable Narrative Generator
```python
class NarrativeReportGenerator:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.insights = self._generate_insights()
        
    def generate_narrative_report(self) -> str:
        """Generate a flowing narrative report"""
        
        sections = [
            self._generate_introduction(),
            self._generate_key_discoveries(),
            self._generate_feature_stories(),
            self._generate_practical_implications(),
            self._generate_technical_recommendations(),
            self._generate_conclusion()
        ]
        
        return "\n\n".join(sections)
    
    def _generate_introduction(self) -> str:
        return f"""
# Understanding Race Feature Behavior Across Rider Percentiles

This analysis examines how {len(self.data['feature_analysis'])} race features behave as we expand our view from the top 30% of riders to include all finishers. Our goal is to understand which features provide stable, reliable signals across different competitive levels and which are specific to elite or broader populations.

## The Big Picture

When analyzing cycling race data, the choice of which riders to include (the "N" parameter) fundamentally affects the patterns we observe. Some features remain remarkably stable whether we look at just the elite riders or the entire field, while others tell completely different stories depending on our perspective.
        """
    
    def _generate_key_discoveries(self) -> str:
        stable_features = self._get_stable_features()
        dilution_features = self._get_dilution_features()
        
        return f"""
## Key Discoveries

### 1. The Stable Core
We identified {len(stable_features)} features that maintain consistent behavior across all N levels. These "stable core" features include {', '.join(stable_features[:3])}, among others. These features appear to capture fundamental race characteristics that transcend competitive level.

**Why this matters**: These features can be reliably used for analysis regardless of whether you're studying elite performances or broader participation patterns.

### 2. The Elite Indicators
{len(dilution_features)} features show strong "dilution" patterns, meaning they have clear signals among top riders that become increasingly noisy as we include more participants. Notable examples include {', '.join(dilution_features[:3])}.

**Insight**: These features likely capture the distinguishing characteristics of elite racing - the patterns that separate the top performers from the rest of the field.

### 3. The Convergence Effect
Several features show interesting "concentration" patterns where variance decreases as we include more riders. This suggests these metrics converge toward population norms and may be less useful for distinguishing between individual races when looking at the full field.
        """
    
    def _generate_feature_stories(self) -> str:
        """Generate narrative descriptions of interesting feature behaviors"""
        
        stories = []
        
        # Find the most interesting features
        interesting_features = self._get_most_interesting_features()
        
        for feature in interesting_features[:3]:
            story = self._generate_feature_story(feature)
            stories.append(story)
        
        return f"""
## Feature Spotlight: Three Revealing Patterns

{chr(10).join(stories)}
        """
    
    def _generate_feature_story(self, feature: str) -> str:
        """Generate a narrative story about a specific feature"""
        
        feat_data = self.data['feature_analysis'][feature]
        pattern = feat_data.get('behavior_pattern', {}).get('primary_pattern', 'unknown')
        
        templates = {
            'dilution': """
### {feature}: The Elite Differentiator

The {feature} metric tells a fascinating story of elite performance. Among the top 30% of riders, this feature shows clear, distinct patterns with high discriminative power. However, as we expand our view to include more riders, the signal becomes increasingly diluted.

At N=30, {feature} achieves a distinctiveness score of {dist_30:.2f}, but this drops to just {dist_100:.2f} when looking at all riders. This {pct_drop:.0f}% decrease suggests that {feature} captures something specific about elite racing dynamics that simply doesn't apply to the broader field.

**Practical Implication**: When analyzing elite performance, {feature} should be weighted heavily. For mass participation events, consider reducing its importance or excluding it entirely.
            """,
            
            'stable': """
### {feature}: The Universal Truth

Remarkably, {feature} maintains consistent behavior whether we're looking at just the elite or the entire field. With a stability score of {stability:.2f}, this feature appears to capture a fundamental aspect of race dynamics that transcends competitive level.

The coefficient of variation for {feature} changes by less than {cv_change:.1f}% across all N levels, and its correlation with other features remains stable (standard deviation < 0.1). This stability makes it a cornerstone feature for any analysis.

**Practical Implication**: {feature} can be confidently used as a primary feature regardless of the competitive level being analyzed. Its universal applicability makes it ideal for models that need to work across different race types and competitive levels.
            """
        }
        
        # Get the appropriate template
        template = templates.get(pattern, templates['stable'])
        
        # Calculate metrics for the story
        dist_trajectory = feat_data.get('distinctiveness', {}).get('trajectory', {})
        dist_30 = dist_trajectory.get(30, {}).get('overall_distinctiveness', 0)
        dist_100 = dist_trajectory.get(100, {}).get('overall_distinctiveness', 0)
        
        return template.format(
            feature=feature.replace('_', ' ').title(),
            dist_30=dist_30,
            dist_100=dist_100,
            pct_drop=(1 - dist_100/dist_30) * 100 if dist_30 > 0 else 0,
            stability=feat_data.get('stability_score', 0),
            cv_change=self._calculate_cv_change(feat_data)
        )
```

### 3. Report Configuration and Templates

```python
class ReportConfiguration:
    """Configuration for different report types"""
    
    REPORT_TEMPLATES = {
        'executive': {
            'sections': ['executive_summary', 'key_findings', 'recommendations'],
            'max_length': 2000,
            'include_visuals': True,
            'technical_level': 'low'
        },
        
        'technical': {
            'sections': ['executive_summary', 'methodology', 'detailed_analysis', 
                        'statistical_results', 'implementation_guide'],
            'max_length': 10000,
            'include_visuals': True,
            'include_code': True,
            'technical_level': 'high'
        },
        
        'llm_consumption': {
            'format': 'json',
            'include_metadata': True,
            'structured_insights': True,
            'include_recommendations': True
        },
        
        'visual_summary': {
            'sections': ['key_visuals', 'caption_narratives'],
            'visual_types': ['heatmap', 'scatter', 'trajectory', 'clustering'],
            'include_interactive': True
        }
    }

class ReportBuilder:
    def __init__(self, analysis_data: Dict[str, Any]):
        self.data = analysis_data
        self.config = ReportConfiguration()
        
    def build_report(self, report_type: str = 'technical') -> Dict[str, Any]:
        """Build a complete report package"""
        
        template = self.config.REPORT_TEMPLATES.get(report_type, {})
        
        report_package = {
            'metadata': {
                'type': report_type,
                'generated': datetime.now().isoformat(),
                'data_summary': self._summarize_data()
            },
            'content': {},
            'visuals': {},
            'exports': {}
        }
        
        # Generate sections based on template
        for section in template.get('sections', []):
            report_package['content'][section] = self._generate_section(section)
        
        # Generate visuals if requested
        if template.get('include_visuals', False):
            report_package['visuals'] = self._generate_all_visuals()
        
        # Generate exports
        report_package['exports'] = {
            'markdown': self._export_markdown(report_package),
            'html': self._export_html(report_package),
            'pdf_ready': self._export_pdf_ready(report_package)
        }
        
        return report_package
```

### 4. Interactive Report Components

```python
class InteractiveReportGenerator:
    """Generate interactive HTML reports with dynamic visualizations"""
    
    def generate_interactive_report(self, data: Dict[str, Any]) -> str:
        """Generate fully interactive HTML report"""
        
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Race Feature Analysis Report</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .section {{ margin-bottom: 30px; }}
        .feature-card {{ 
            border: 1px solid #ddd; 
            padding: 15px; 
            margin: 10px 0;
            border-radius: 5px;
        }}
        .metric {{ 
            display: inline-block; 
            margin: 5px 15px;
            padding: 5px 10px;
            background: #f0f0f0;
            border-radius: 3px;
        }}
        .tier-1 {{ background-color: #4CAF50; color: white; }}
        .tier-2 {{ background-color: #8BC34A; }}
        .tier-3 {{ background-color: #FFC107; }}
        .tier-4 {{ background-color: #FF9800; }}
    </style>
</head>
<body>
    <h1>Race Feature N-Spectrum Analysis</h1>
    
    <div class="section" id="executive-summary">
        {executive_summary}
    </div>
    
    <div class="section" id="interactive-explorer">
        <h2>Interactive Feature Explorer</h2>
        <div id="feature-selector">
            <label>Select Feature: 
                <select id="feature-dropdown">
                    {feature_options}
                </select>
            </label>
        </div>
        <div id="feature-details"></div>
        <div id="feature-plot"></div>
    </div>
    
    <div class="section" id="comparative-analysis">
        {comparative_plots}
    </div>
    
    <script>
        {interactive_js}
    </script>
</body>
</html>
        """
        
        return html_template.format(
            executive_summary=self._generate_executive_summary_html(data),
            feature_options=self._generate_feature_options(data),
            comparative_plots=self._generate_comparative_plots(data),
            interactive_js=self._generate_interactive_javascript(data)
        )
```

## Output Examples

### 1. Executive Summary Format
```markdown
# Race Feature Analysis: Executive Summary

**Analysis Date**: 2024-01-15
**Total Features Analyzed**: 37
**Key Finding**: 12 features show stable behavior across all N levels

## Top 5 Insights
1. **Abandonment ratio** is highly discriminative among elite riders (N=30) but becomes noise at N=100
2. **Winning time** remains stable and informative across all N levels
3. Features can be reduced by 40% while maintaining 95% of predictive power
4. Optimal N combination is [30, 50, 70, 90] for balanced analysis
5. 8 feature pairs show >0.95 correlation and can be deduplicated

## Recommended Action
Implement tiered feature selection based on the target population:
- Elite analysis: Use all 37 features at N=30, 40
- General analysis: Use 22 core features at N=50, 70, 90
- Quick analysis: Use 15 stable features at N=70
```

### 2. LLM-Optimized JSON Structure
```json
{
  "analysis_summary": {
    "stable_core_features": ["winning_time", "total_finishers", "abandon_ratio"],
    "n_sensitive_features": ["variance_normalized", "skewness_absolute"],
    "redundant_pairs": [["variance_absolute", "std_deviation_absolute"]],
    "optimal_n_levels": [30, 50, 70, 90]
  },
  "feature_recommendations": {
    "winning_time": {
      "action": "always_include",
      "reason": "stable_across_n",
      "quality_score": 0.95
    }
  }
}
```

This reporter design provides:
1. Multiple output formats (markdown, HTML, JSON, PDF-ready)
2. Both human-readable narratives and structured data for LLMs
3. Interactive visualizations for exploring the data
4. Configurable report types for different audiences
5. Automated insight generation and storytelling