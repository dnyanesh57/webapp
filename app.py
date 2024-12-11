import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.dependencies import Input, Output, State
from dash_color_picker import ColorPicker
import plotly.graph_objs as go
import pandas as pd
import requests
from io import StringIO

# Function to process each file and create a DataFrame
def process_file(file_url):
    response = requests.get(file_url, verify=False)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text), sep=" ", header=None, names=['ID', 'Date', 'Time', 'Temp', 'Humidity'])
    df['Temp'] = pd.to_numeric(df['Temp'])
    df['Humidity'] = pd.to_numeric(df['Humidity'])
    df['Datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d-%m-%y %H:%M:%S')
    df['Time_Diff'] = df['Datetime'].diff().fillna(pd.Timedelta(seconds=0)).dt.total_seconds()
    df['Cumulative_Time'] = df['Time_Diff'].cumsum()
    df['Cumulative_Hours'] = (df['Cumulative_Time'] / 3600).round(2)

    return df

# Create the Dash app
app = dash.Dash(__name__)

# App layout
app.layout = html.Div([
    html.H1("Interactive Temperature Profile Plotter", style={"textAlign": "center"}),

    # Input Section
    html.Div([
        html.Div([
            html.Label("Meter ID"),
            dcc.Input(id="meter-id", type="text", placeholder="Enter Meter ID", debounce=True),
        ], style={"display": "inline-block", "marginRight": "10px"}),

        html.Div([
            html.Label("Sensor ID"),
            dcc.Input(id="sensor-id", type="text", placeholder="Enter Sensor ID", debounce=True),
        ], style={"display": "inline-block", "marginRight": "10px"}),

        html.Div([
            html.Label("Legend"),
            dcc.Input(id="legend", type="text", placeholder="Enter Legend"),
        ], style={"display": "inline-block", "marginRight": "10px"}),

        html.Div([
            html.Label("Color"),
            ColorPicker(id="color-picker", color='#000000'),  # Use 'color' instead of 'defaultValue'
        ], style={"display": "inline-block", "marginRight": "10px"}),

        # Button for updating the table
        html.Button("Update Table", id="update-table", n_clicks=0),
        # Button for plotting the graph
        html.Button("Plot Graph", id="plot-graph", n_clicks=0),
        # Button to show summary
        html.Button("Show Summary", id="show-summary", n_clicks=0),
    ], style={"marginBottom": "20px"}),

    # Data Table
    html.Div([
        dash_table.DataTable(
            id="sensor-table",
            columns=[
                {"name": "Meter ID", "id": "meter_id", "editable": True},
                {"name": "Sensor ID", "id": "sensor_id", "editable": True},
                {"name": "Legend", "id": "legend", "editable": True},
                {"name": "Color", "id": "color", "editable": True},
            ],
            data=[],  # Initially empty
            editable=True,
            row_deletable=True,
        )
    ], style={"marginBottom": "20px"}),

    # Graph Title Input
    html.Div([
        html.Label("Graph Title"),
        dcc.Input(id="graph-title", type="text", placeholder="Enter Graph Title", debounce=True),
    ], style={"marginBottom": "20px"}),

    # Plot Section
    html.Div([
        dcc.Graph(id="temperature-plot", style={"height": "600px"})
    ]),

    # Summary Section
    html.Div(id="summary-section", style={"marginTop": "20px"}),
])

# Combined callback to handle both updating table, plotting graph, and showing summary
@app.callback(
    [Output("sensor-table", "data"),
     Output("temperature-plot", "figure"),
     Output("summary-section", "children")],
    [Input("update-table", "n_clicks"),
     Input("plot-graph", "n_clicks"),
     Input("show-summary", "n_clicks")],
    State("meter-id", "value"),
    State("sensor-id", "value"),
    State("legend", "value"),
    State("color-picker", "color"),
    State("sensor-table", "data"),
    State("graph-title", "value"),
    prevent_initial_call=True,
)
def update_table_and_plot(update_clicks, plot_clicks, summary_clicks, meter_id, sensor_id, legend, color, existing_data, title):
    ctx = dash.callback_context

    if not ctx.triggered:
        return existing_data, {}, ""

    trigger = ctx.triggered[0]['prop_id'].split('.')[0]

    # Initialize response
    updated_data = existing_data
    plot_figure = {}
    summary_text = ""

    if trigger == "update-table" and update_clicks > 0:
        if meter_id and sensor_id and legend:
            new_row = {
                "meter_id": meter_id,
                "sensor_id": sensor_id,
                "legend": legend,
                "color": color,
            }
            updated_data = existing_data + [new_row]

    elif trigger == "plot-graph" and plot_clicks > 0:
        traces = []
        for row in updated_data:
            meter_id = row["meter_id"]
            sensor_id = row["sensor_id"]
            file_url = f'https://fileserv.c-probe.in/{meter_id}_{sensor_id}.txt'  # URL for sensor data
            legend = row["legend"]
            color = row["color"]

            df = process_file(file_url)
            traces.append(go.Scatter(
                x=df['Cumulative_Hours'],  
                y=df['Temp'],  
                mode='lines',  
                name=legend,  
                line=dict(color=color),
                hovertemplate='<b>Cumulative Time: %{x} hours</b><br>' +
                                'Temperature: %{y}°C<br>' +
                                '<extra></extra>',  
            ))

        plot_title = title if title else "Temperature Profile"
        layout = go.Layout(
            title=plot_title,
            xaxis=dict(title="Cumulative Time (Hours)"),
            yaxis=dict(title="Temperature (°C)"),
            hovermode="closest",
        )
        plot_figure = {"data": traces, "layout": layout}

    elif trigger == "show-summary" and summary_clicks > 0:
        # Calculate max and min temp and their corresponding times
        max_temp_info = None
        min_temp_info = None
        for row in updated_data:
            meter_id = row["meter_id"]
            sensor_id = row["sensor_id"]
            file_url = f'https://fileserv.c-probe.in/{meter_id}_{sensor_id}.txt'  # URL for sensor data

            df = process_file(file_url)
            
            max_temp = df['Temp'].max()
            max_temp_time = df.loc[df['Temp'] == max_temp, 'Datetime'].iloc[0]
            min_temp = df['Temp'].min()
            min_temp_time = df.loc[df['Temp'] == min_temp, 'Datetime'].iloc[0]

            max_temp_info = f"Max Temp: {max_temp}°C at {max_temp_time}"
            min_temp_info = f"Min Temp: {min_temp}°C at {min_temp_time}"

        summary_text = html.Div([
            html.H4("Summary:"),
            html.P(max_temp_info),
            html.P(min_temp_info),
        ])

    return updated_data, plot_figure, summary_text


if __name__ == "__main__":
    app.run_server(debug=True)
