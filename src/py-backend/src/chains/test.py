import os
import uuid
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

import seaborn as sns
from qbstyles import mpl_style

mpl_style(dark=True)

import matplotlib as mpl

DEFAULT_STYLE = {
    "node_color": mpl.rcParams['axes.facecolor'],
    "edge_color": mpl.rcParams['grid.color'],
    "font_color": mpl.rcParams['text.color'],
    "font_size": mpl.rcParams['font.size'],
}

APPDATA_PATH = Path(os.getenv("APPDATA", Path.home()))
PLOT_DIR = APPDATA_PATH / "personal-query" / "plots"

print(plt.style.available)

filename = f"{uuid.uuid4().hex}.png"
full_path = PLOT_DIR / filename

from database import get_db

query = """SELECT 
  prev_activity AS "From",
  activity AS "To",
  COUNT(*) AS switch_count
FROM (
  SELECT tsStart, activity,
         LAG(activity) OVER (ORDER BY tsStart) AS prev_activity
  FROM window_activity
  WHERE tsStart >= '2025-06-24 00:00:00' AND tsStart < '2025-06-25 00:00:00'
)
WHERE activity != prev_activity
GROUP BY prev_activity, activity
ORDER BY switch_count DESC
LIMIT 20;"""
db = get_db()
try:
    result = db._execute(query)
except Exception as e:
    print(e)

df = pd.DataFrame(result)

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

# Prepare the data for visualization
df_sorted = df.sort_values('switch_count', ascending=False)

# Set up the plot
plt.figure(figsize=(12, 8))
sns.set_style("whitegrid")
palette = sns.color_palette("husl", n_colors=len(df_sorted))

# Create horizontal bar plot
ax = sns.barplot(data=df_sorted, y='From', x='switch_count', hue='To',
                 palette=palette, dodge=False)

# Customize the plot
plt.title("Top Context Switches on Tuesday, June 24, 2025", pad=20, fontsize=14)
plt.xlabel("Number of Switches", labelpad=10)
plt.ylabel("From Activity", labelpad=10)
plt.legend(title='To Activity', bbox_to_anchor=(1.05, 1), loc='upper left')

# Rotate long labels and adjust layout
plt.xticks(rotation=45, ha='right')
plt.tight_layout()

# Save and close
plt.savefig(full_path)
plt.close()
