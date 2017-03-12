# coding=utf-8
from mycodo.databases import CRUDMixin
from mycodo.mycodo_flask.extensions import db


class Graph(CRUDMixin, db.Model):
    __tablename__ = "graph"
    id = db.Column(db.Integer, unique=True, primary_key=True)
    name = db.Column(db.Text, default='Graph')
    pid_ids = db.Column(db.Text, default='')  # store IDs and measurements to display
    relay_ids = db.Column(db.Text, default='')  # store IDs and measurements to display
    sensor_ids_measurements = db.Column(db.Text, default='')  # store IDs and measurements to display
    width = db.Column(db.Integer, default=100)  # Width of page (in percent)
    height = db.Column(db.Integer, default=400)  # Height (in pixels)
    x_axis_duration = db.Column(db.Integer, default=1440)  # X-axis duration (in minutes)
    refresh_duration = db.Column(db.Integer, default=120)  # How often to add new data and redraw graph
    enable_navbar = db.Column(db.Boolean, default=False)  # Show navigation bar
    enable_rangeselect = db.Column(db.Boolean, default=False)  # Show range selection buttons
    enable_export = db.Column(db.Boolean, default=False)  # Show export menu
    use_custom_colors = db.Column(db.Boolean, default=False)  # Enable custom colors of graph series
    custom_colors = db.Column(db.Text, default='')  # Custom hex color values (csv)

    def __reper__(self):
        return "<{cls}(id={s.id})>".format(s=self, cls=self.__class__.__name__)
