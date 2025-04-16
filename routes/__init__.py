from flask import Flask

def create_app():
    app = Flask(__name__)

    # Register routes here
    from .chart_type import chart_type_analysis
    app.add_url_rule('/chart_type_analysis', 'chart_type_analysis', chart_type_analysis)

    return app
