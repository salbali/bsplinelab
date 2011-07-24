#!/usr/bin/env python
"""
Allows editing of a line plot.

Left-dragging a point will move its position.

Right-drag pans the plot.

Mousewheel up and down zooms the plot in and out.

Pressing "z" brings up the Zoom Box, and you can click-drag a rectangular region to
zoom.  If you use a sequence of zoom boxes, pressing alt-left-arrow and
alt-right-arrow moves you forwards and backwards through the "zoom history".
"""

# Major library imports
import numpy as np
from scipy.special import jn

from enthought.chaco.example_support import COLOR_PALETTE

# Enthought library imports
from enthought.enable.tools.api import DragTool
from enthought.enable.api import Component, ComponentEditor, Window
from enthought.traits.api import HasTraits, Instance, Int, Tuple, on_trait_change, Array, List, ListFloat, Float, CFloat, Str
from enthought.traits.ui.api import Item, Group, View, TextEditor

# Chaco imports
from enthought.chaco.api import add_default_axes, add_default_grids, OverlayPlotContainer, PlotLabel, ScatterPlot, create_line_plot, LinePlot, ArrayPlotData, Plot, palette14, palette11
from enthought.chaco.tools.api import PanTool, ZoomTool

from spline import BSpline

class PointDraggingTool(DragTool):

	component = Instance(Component)

	# The pixel distance from a point that the cursor is still considered
	# to be 'on' the point
	threshold = Int(5)

	# The index of the point being dragged
	_drag_index = Int(-1)

	# The original dataspace values of the index and value datasources
	# corresponding to _drag_index
	_orig_value = Tuple

	def is_draggable(self, x, y):
		# Check to see if (x,y) are over one of the points in self.component
		if self._lookup_point(x, y) is not None:
			return True
		else:
			return False

	def normal_mouse_move(self, event):
		plot = self.component

		ndx = plot.map_index((event.x, event.y), self.threshold)
		if ndx is None:
			if plot.index.metadata.has_key('selections'):
				del plot.index.metadata['selections']
		else:
			plot.index.metadata['selections'] = [ndx]

		plot.invalidate_draw()
		plot.request_redraw()


	def drag_start(self, event):
		plot = self.component
		ndx = plot.map_index((event.x, event.y), self.threshold)
		if ndx is None:
			return
		self._drag_index = ndx
		self._orig_value = (plot.index.get_data()[ndx], plot.value.get_data()[ndx])

	def dragging(self, event):
		plot = self.component

		data_x, data_y = plot.map_data((event.x, event.y))

		plot.index._data[self._drag_index] = data_x
		plot.value._data[self._drag_index] = data_y
		plot.index.data_changed = True
		plot.value.data_changed = True
		plot.request_redraw()

	def drag_cancel(self, event):
		plot = self.component
		plot.index._data[self._drag_index] = self._orig_value[0]
		plot.value._data[self._drag_index] = self._orig_value[1]
		plot.index.data_changed = True
		plot.value.data_changed = True
		plot.request_redraw()

	def drag_end(self, event):
		plot = self.component
		if plot.index.metadata.has_key('selections'):
			del plot.index.metadata['selections']
		plot.invalidate_draw()
		plot.request_redraw()

	def _lookup_point(self, x, y):
		""" Finds the point closest to a screen point if it is within self.threshold

		Parameters
		==========
		x : float
			screen x-coordinate
		y : float
			screen y-coordinate

		Returns
		=======
		(screen_x, screen_y, distance) of datapoint nearest to the input *(x,y)*.
		If no data points are within *self.threshold* of *(x,y)*, returns None.
		"""

		if hasattr(self.component, 'get_closest_point'):
			# This is on BaseXYPlots
			return self.component.get_closest_point((x,y), threshold=self.threshold)

		return None

class StrListFloat(List):
	def validate(self, object, name, value):
		if isinstance(value, basestring):
			try:
				list_value = eval(value)
			except SyntaxError:
				self.error(object, name, value)
		else:
			list_value = value
		validated_value = super(StrListFloat, self).validate(object, name, list_value)
		return validated_value


#===============================================================================
# # Create the Chaco plot.
#===============================================================================
#===============================================================================
# Attributes to use for the plot view.
size=(700,600)
title="BSpline"
#===============================================================================
# # Demo class that is used by the demo.py application.
#===============================================================================
class BSplineLab(HasTraits):
	plot_data = Instance(ArrayPlotData)
	plot = Instance(Component)
	knots = StrListFloat()

	traits_view = View(
					Group(
						Item('plot', editor=ComponentEditor(size=size),
							show_label=False),
						Item('knots', editor=TextEditor()),
						orientation = "vertical",),
					resizable=True, title=title
					)


	def __init__(self, control_points, knots):
		self._set_control_points(control_points)
		self._setup_plot()
		self.spline_renderers = []
		self.on_trait_change(self._update_spline_points, 'knots')
		self._set_knots(knots)

	def _set_control_points(self, control_points):
		# Create the initial data
		control_points = np.array(control_points)
		y = control_points[:,1]
		x = control_points[:,0]
		controls = ArrayPlotData(x=x, y=y,)
		self.plot_data = controls

	def _set_knots(self, knots):
		self.knots = knots

	def plot_points(self, control_matrix):
		b = BSpline(control_matrix, self.knots)
		b.plotres = 300
		self._bspline = b
		vlist = list(v for (t,k,v) in b.generate_points())
		return vlist

	palette = palette14

	def _add_spline_points(self, plot_data,):
		control_matrix = np.vstack([plot_data.arrays['x'], plot_data.arrays['y']]).T
		vlist = self.plot_points(control_matrix)
		# remove existing spline renderers
		self.plot.remove(*self.spline_renderers)
		# rebuild a new list of spline renderers
		def gen_renderers():
			for index, values in enumerate(vlist):
				xname = 'xp[{}]'.format(index)
				yname = 'yp[{}]'.format(index)
				plot_data.set_data(name=xname, new_data=values[:,0])
				plot_data.set_data(name=yname, new_data=values[:,1])
				spline_renderer, = self.plot_factory.plot([xname,yname], color=self.palette[index % len(self.palette)], line_width=3.)
				yield spline_renderer
		self.spline_renderers = list(gen_renderers())
		self.plot.add(*self.spline_renderers)
		self.plot.request_redraw()

	def _update_spline_points(self):
		self._add_spline_points(self.plot_data,)

	def _setup_plot(self):
		container = OverlayPlotContainer(padding = 50, fill_padding = True,
										bgcolor = "lightgray", use_backbuffer=True)


		plot_factory = Plot(self.plot_data)
		self.plot_factory = plot_factory

		#lineplot = create_line_plot((x,y), color=tuple(COLOR_PALETTE[0]), width=2.0)
		lineplot, = plot_factory.plot(['x','y'])

		lineplot.selected_color = "none"
		#scatter = ScatterPlot(index = lineplot.index,
						#value = lineplot.value,
						#index_mapper = lineplot.index_mapper,
						#value_mapper = lineplot.value_mapper,
						#color = tuple(COLOR_PALETTE[0]),
						#marker_size = 5)
		scatter, = plot_factory.plot(['x','y'], type='scatter', color= tuple(COLOR_PALETTE[0]), marker_size=5)
		scatter.index.sort_order = "ascending"

		scatter.on_trait_change(self._update_spline_points, 'index.data_changed')
		scatter.on_trait_change(self._update_spline_points, 'value.data_changed')

		scatter.bgcolor = "white"
		scatter.border_visible = True

		add_default_grids(scatter)
		add_default_axes(scatter)

		scatter.tools.append(PanTool(scatter, drag_button="right"))

		# The ZoomTool tool is stateful and allows drawing a zoom
		# box to select a zoom region.
		zoom = ZoomTool(scatter, tool_mode="box", always_on=False, drag_button=None)
		scatter.overlays.append(zoom)

		scatter.tools.append(PointDraggingTool(scatter))

		container.add(lineplot)
		container.add(scatter)

		# Add the title at the top
		container.overlays.append(PlotLabel("BSpline Lab",
								component=container,
								font = "swiss 16",
								overlay_position="top"))

		self.plot = container


butterfly = {
	'control_points': [[0.7,-0.4],[1.0,-0.4],[2.5,-1.2],[3.2,-.5],[-0.2,-.5],[.5,-1.2],[2.0,-.4],[2.3,-.4]],
	'knots': [1.,1.,1.,1.2,1.4,1.6,1.8,2.,2.,2.],
	}

control_points = np.array([[1.3,2], [2,3], [1.8,5], [1,6], [2,2]])
knots = [0.,0.2,0.5,0.8,1.2,1.5,]#1.8,2]

demo = BSplineLab(**butterfly)

if __name__ == "__main__":
	demo.configure_traits()
