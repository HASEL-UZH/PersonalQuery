"""Monkey Patch - Python code for plot generation"""
import matplotlib as mpl
import plotly.io as pio
from qbstyles import mpl_style
import networkx as nx
from matplotlib import pyplot as plt
from matplotlib import cm, colors as mcolors
import plotly.io as pio
from qbstyles import mpl_style

# Apply global style
mpl_style(dark=True)
pio.templates.default = "plotly_dark"


# Define style defaults from rcParams
def apply_global_style():
    mpl_style(dark=True)
    pio.templates.default = "plotly_dark"
    plt.rcParams['font.family'] = ['DejaVu Sans', 'Noto Color Emoji']  # emoji-compatible


DEFAULT_PALETTE = cm.get_cmap('tab20').colors


def get_node_colors(n):
    return [DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)] for i in range(n)]


def get_edge_color():
    return 'white'


def get_text_color():
    return 'white'


def get_edge_widths(weights, scale=4):
    max_w = max(weights) if weights else 1
    return [w / max_w * scale for w in weights]


_original_nodes = nx.draw_networkx_nodes
_original_edges = nx.draw_networkx_edges
_original_labels = nx.draw_networkx_labels


def patched_draw_nodes(g, pos, *args, **kwargs):
    kwargs.setdefault('node_color', get_node_colors(len(g.nodes())))
    kwargs.setdefault('edgecolors', 'black')
    return _original_nodes(g, pos, *args, **kwargs)


def patched_draw_edges(g, pos, *args, **kwargs):
    edge_weights = [g[u][v].get('switch_count', 1) for u, v in g.edges()]
    kwargs.setdefault('edge_color', get_edge_color())
    kwargs.setdefault('width', get_edge_widths(edge_weights))
    kwargs.setdefault('alpha', 0.7)
    return _original_edges(g, pos, *args, **kwargs)


def patched_draw_labels(g, pos, *args, **kwargs):
    kwargs.setdefault('font_color', get_text_color())
    return _original_labels(g, pos, *args, **kwargs)
