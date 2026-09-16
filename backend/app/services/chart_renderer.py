"""Fixed, isolated static chart renderer. Never evaluates model-supplied code."""
import io
import json
import os
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    font = FontProperties(fname=font_path) if os.path.exists(font_path) else FontProperties()
    option = json.load(sys.stdin)["option"]
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=120)
    colors = ["#32776a", "#c59d53", "#84b6a3", "#52677e"]
    x_axis = option.get("xAxis", {})
    labels = x_axis.get("data", []) if isinstance(x_axis, dict) else []
    for index, series in enumerate(option["series"]):
        color = colors[index % len(colors)]
        data = series["data"]
        values = [item.get("value") if isinstance(item, dict) else item for item in data]
        name = str(series.get("name", ""))
        if series["type"] == "pie":
            wedges, _ = ax.pie(values, colors=colors)
            ax.legend(wedges, [str(item.get("name", i)) for i, item in enumerate(data)], prop=font)
            break
        if series["type"] == "scatter":
            ax.scatter([item[0] for item in values], [item[1] for item in values], label=name, color=color)
        elif series["type"] == "bar":
            width = .8 / len(option["series"])
            ax.bar([i + index * width for i in range(len(values))], values, width=width, label=name, color=color)
        else:
            ax.plot(range(len(values)), values, label=name, color=color)
    if labels and option["series"][0]["type"] != "pie":
        step = max(1, len(labels) // 10)
        ticks = list(range(0, len(labels), step))
        ax.set_xticks(ticks, [str(labels[i])[:50] for i in ticks], rotation=20, fontproperties=font)
    title = option.get("title", {})
    ax.set_title(str(title.get("text", "Analysis"))[:150] if isinstance(title, dict) else "Analysis", fontproperties=font)
    if option["series"][0]["type"] != "pie":
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.15)
        if any(s.get("name") for s in option["series"]):
            ax.legend(prop=font)
    fig.tight_layout()
    output = io.BytesIO()
    fig.savefig(output, format="png", facecolor="white")
    plt.close(fig)
    sys.stdout.buffer.write(output.getvalue())


if __name__ == "__main__":
    main()
