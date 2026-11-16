from lightweight_charts import Chart

def on_click(chart, event):
    print("Click event:", event)

if __name__ == '__main__':
    chart = Chart()
    chart.events.click += on_click
    chart.show(block=True)
