from lightweight_charts import Chart

def on_line_move(line):
    print("Line moved to:", line.price)

if __name__ == '__main__':
    chart = Chart()
    chart.horizontal_line(100, func=on_line_move)
    chart.show(block=True)
