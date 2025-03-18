import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict, Union
import matplotlib.ticker as mticker
from scipy.stats import gaussian_kde

def visualize_single_race_stats(race_stats: Dict, title: str = None, figsize: tuple = (10, 8), save_path: str = None):
    """
    Create a visualization of finishing times for a single race with statistical measures.
    
    Args:
        race_stats: Dictionary produced by create_stat_measures_race function
        title: Optional title for the plot (defaults to 'Race Finishing Times Distribution')
        figsize: Figure size as tuple (width, height)
        save_path: Path to save the figure (if None, figure is displayed but not saved)
        
    Returns:
        matplotlib figure object
    """
    if not race_stats or 'finishing_times' not in race_stats:
        raise ValueError("Invalid race_stats dictionary provided")
    
    # Normalize times relative to winning time
    winning_time = race_stats['finishing_times'][0]
    normalized_times = [time / winning_time for time in race_stats['finishing_times']]
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create histogram
    n, bins, patches = ax.hist(normalized_times, bins=100, alpha=0.75, color='steelblue', 
                             edgecolor='black', linewidth=0.8)
    
    # Set title and labels
    ax.set_title(title or "Race Finishing Times Distribution", fontsize=16, pad=20)
    ax.set_xlabel("Normalized Finishing Time (winner = 1.0)", fontsize=12)
    ax.set_ylabel("Number of Riders", fontsize=12)
    
    # Format x-axis as percentage
    def percentage_formatter(x, pos):
        return f"{(x-1)*100:.1f}%"
    
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(percentage_formatter))
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Add statistical measures as text annotation
    stats_text = "\n".join([
        f"Statistical Measures:",
        f"Std Dev: {race_stats['normalized_standard_deviation']:.4f}",
        f"Skewness: {race_stats['normalized_skewness']:.4f}",
        f"Kurtosis: {race_stats['normalized_kurtosis']:.4f}",
        f"Gini Coeff: {race_stats['normalized_gini_coefficient']:.4f}",
        f"Shannon Entropy: {race_stats['normalized_shannon_entropy']:.4f}"
    ])
    
    # Position text in the upper right
    ax.text(0.95, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Adjust layout
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    return fig


def compare_multiple_races(race_stats_list: List[Dict], 
                          race_names: List[str] = None,
                          title: str = "Comparison of Race Finishing Time Distributions",
                          figsize: tuple = (12, 8),
                          use_kde: bool = True,
                          save_path: str = None):
    """
    Create a visualization comparing finishing time distributions for multiple races.
    
    Args:
        race_stats_list: List of dictionaries produced by create_stat_measures_race function
        race_names: Optional list of race names for the legend (defaults to Race 1, Race 2, etc.)
        title: Plot title
        figsize: Figure size as tuple (width, height)
        use_kde: If True, use kernel density estimation instead of histograms
        save_path: Path to save the figure (if None, figure is displayed but not saved)
        
    Returns:
        matplotlib figure object
    """
    if not race_stats_list or not all('finishing_times' in stats for stats in race_stats_list):
        raise ValueError("Invalid race_stats_list provided")
    
    # Create default race names if not provided
    if race_names is None:
        race_names = [f"Race {i+1}" for i in range(len(race_stats_list))]
    
    # Ensure we have the same number of names as races
    if len(race_names) != len(race_stats_list):
        raise ValueError("Number of race names must match number of races")
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot each race
    for i, race_stats in enumerate(race_stats_list):
        # Normalize times relative to winning time
        winning_time = race_stats['finishing_times'][0]
        normalized_times = [time / winning_time for time in race_stats['finishing_times']]
        
        if use_kde:
            # Use kernel density estimation for smoother comparison
            density = gaussian_kde(normalized_times)
            x = np.linspace(min(normalized_times), max(normalized_times), 1000)
            ax.plot(x, density(x), label=race_names[i])
        else:
            # Use histograms with transparency and sensible normalization
            counts, bins, _ = ax.hist(normalized_times, bins=100, alpha=0.3, 
                                    label=race_names[i], histtype='stepfilled', 
                                    density=True)
        
        # Scale down the y-axis for more intuitive values
        #ax.set_ylim(0, min(max(counts) * 1.1, 10))  # Cap at 10 for readability
    
    # Format x-axis as percentage
    def percentage_formatter(x, pos):
        return f"{(x-1)*100:.1f}%"
    
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(percentage_formatter))
    
    # Set title and labels
    ax.set_title(title, fontsize=16, pad=20)
    ax.set_xlabel("Normalized Finishing Time (winner = 1.0)", fontsize=12)
    
    if use_kde:
        ax.set_ylabel("Density", fontsize=12)
    else:
        ax.set_ylabel("Probability Density", fontsize=12)
    
    # Add grid and legend
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper right', frameon=True, framealpha=0.9)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save if path provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    return fig
