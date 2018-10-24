"""
Defines Layout classes which may be used to arrange panes and widgets
in flexible ways to build complex dashboards.
"""
from __future__ import absolute_import

import param

from bokeh.layouts import (Column as BkColumn, Row as BkRow,
                           WidgetBox as BkWidgetBox, Spacer as BkSpacer)
from bokeh.models.widgets import Tabs as BkTabs, Panel as BkPanel

from .util import push
from .viewable import Reactive, Viewable


class Panel(Reactive):
    """
    Abstract baseclass for a layout of Viewables.
    """

    objects = param.List(default=[], doc="""
        The list of child objects that make up the layout.""")

    _bokeh_model = None

    __abstract = True

    _rename = {'objects': 'children'}

    _linked_props = []

    def __init__(self, *objects, **params):
        from .pane import panel
        objects = [panel(pane) for pane in objects]
        super(Panel, self).__init__(objects=objects, **params)

    def _init_properties(self):
        properties = {k: v for k, v in self.param.get_param_values()
                      if v is not None}
        del properties['objects']
        return self._process_param_change(properties)

    def _link_params(self, model, params, doc, root, comm=None):
        def set_value(*events):
            msg = {event.name: event.new for event in events}
            events = {event.name: event for event in events}
            if 'objects' in msg:
                old = events['objects'].old
                msg['objects'] = self._get_objects(model, old, doc, root, comm)
            msg = self._process_param_change(msg)

            def update_model():
                model.update(**msg)

            if comm:
                update_model()
                push(doc, comm)
            else:
                doc.add_next_tick_callback(update_model)

        ref = model.ref['id']
        watcher = self.param.watch(set_value, params)
        self._callbacks[ref].append(watcher)

    def _cleanup(self, model=None, final=False):
        super(Panel, self)._cleanup(model, final)
        if model is not None:
            for p, c in zip(self.objects, model.children):
                p._cleanup(c, final)

    def select(self, selector=None):
        """
        Iterates over the Viewable and any potential children in the
        applying the Selector.

        Arguments
        ---------
        selector: type or callable or None
            The selector allows selecting a subset of Viewables by
            declaring a type or callable function to filter by.

        Returns
        -------
        viewables: list(Viewable)
        """
        objects = super(Panel, self).select(selector)
        for obj in self.objects:
            objects += obj.select(selector)
        return objects

    def _get_objects(self, model, old_objects, doc, root, comm=None):
        """
        Returns new child models for the layout while reusing unchanged
        models and cleaning up any dropped objects.
        """
        from .pane import panel
        old_children = getattr(model, self._rename.get('objects', 'objects'))
        new_models = []
        for i, pane in enumerate(self.objects):
            pane = panel(pane, _temporary=True)
            self.objects[i] = pane
            if pane in old_objects:
                child = old_children[old_objects.index(pane)]
            else:
                child = pane._get_model(doc, root, model, comm)
            new_models.append(child)

        for pane, old_child in zip(old_objects, old_children):
            if old_child not in new_models:
                pane._cleanup(old_child)
        return new_models

    def _get_model(self, doc, root=None, parent=None, comm=None):
        model = self._bokeh_model()
        root = model if root is None else root
        objects = self._get_objects(model, [], doc, root, comm)

        # HACK ALERT: Insert Spacer if last item in Column has no height
        if isinstance(self, Column) and objects and getattr(objects[-1], 'height', False) is None:
            objects.append(BkSpacer(height=50))

        props = dict(self._init_properties(), objects=objects)
        model.update(**self._process_param_change(props))
        params = [p for p in self.params() if p != 'name']
        self._link_params(model, params, doc, root, comm)
        self._link_props(model, self._linked_props, doc, root, comm)
        return model

    def __getitem__(self, index):
        return self.objects[index]

    def __len__(self):
        return len(self.objects)

    def __contains__(self, obj):
        return obj in self.objects

    def __setitem__(self, index, pane):
        from .pane import panel
        new_objects = list(self.objects)
        new_objects[index] = panel(pane)
        self.objects = new_objects

    def append(self, pane):
        from .pane import panel
        new_objects = list(self.objects)
        new_objects.append(panel(pane))
        self.objects = new_objects

    def insert(self, index, pane):
        from .pane import panel
        new_objects = list(self.objects)
        new_objects.insert(index, panel(pane))
        self.objects = new_objects

    def pop(self, index):
        new_objects = list(self.objects)
        if index in new_objects:
            index = new_objects.index(index)
        new_objects.pop(index)
        self.objects = new_objects


class Row(Panel):
    """
    Horizontal layout of Viewables.
    """

    _bokeh_model = BkRow


class Column(Panel):
    """
    Vertical layout of Viewables.
    """

    _bokeh_model = BkColumn


class WidgetBox(Panel):
    """
    Box to group widgets.
    """

    height = param.Integer(default=None, bounds=(0, None))

    width = param.Integer(default=None, bounds=(0, None))

    _bokeh_model = BkWidgetBox

    def _get_objects(self, model, old_objects, doc, root, comm=None):
        """
        Returns new child models for the layout while reusing unchanged
        models and cleaning up any dropped objects.
        """
        from .pane import panel
        old_children = getattr(model, self._rename.get('objects', 'objects'))
        new_models = []
        for i, pane in enumerate(self.objects):
            pane = panel(pane)
            self.objects[i] = pane
            if pane in old_objects:
                child = old_children[old_objects.index(pane)]
            else:
                child = pane._get_model(doc, root, model, comm)
            if isinstance(child, BkWidgetBox):
                new_models += child.children
            else:
                new_models.append(child)

        for pane, old_child in zip(old_objects, old_children):
            if old_child not in new_models:
                pane._cleanup(old_child, pane._temporary)
        return new_models


class Tabs(Panel):
    """
    Panel of Viewables to be displayed in separate tabs.
    """

    active = param.Integer(default=0, doc="""
        Number of the currently active tab.""")

    objects = param.List(default=[], doc="""
        The list of child objects that make up the tabs.""")

    height = param.Integer(default=None, bounds=(0, None))

    width = param.Integer(default=None, bounds=(0, None))

    _bokeh_model = BkTabs

    _rename = {'objects': 'tabs'}

    _linked_props = ['active']

    def __init__(self, *items, **params):
        from .pane import panel
        objects = []
        for pane in items:
            if isinstance(pane, tuple):
                name, pane = pane
            elif isinstance(pane, Viewable):
                name = pane.name
            else:
                name = None
            objects.append(panel(pane, name=name))
        super(Tabs, self).__init__(*objects, **params)

    def _get_objects(self, model, old_objects, doc, root, comm=None):
        """
        Returns new child models for the layout while reusing unchanged
        models and cleaning up any dropped objects.
        """
        old_children = getattr(model, self._rename.get('objects', 'objects'))
        new_models = []
        for i, pane in enumerate(self.objects):
            if pane in old_objects:
                child = old_children[old_objects.index(pane)]
            else:
                child = pane._get_model(doc, root, model, comm)
                name = pane[0].name if isinstance(pane, Panel) and len(pane) == 1 else pane.name
                child = BkPanel(title=name, child=child)
            new_models.append(child)

        for pane, old_child in zip(old_objects, old_children):
            if old_child not in new_models:
                pane._cleanup(old_child.child, pane._temporary)

        return new_models

    def __setitem__(self, index, pane):
        from .pane import panel
        name = None
        if isinstance(pane, tuple):
            name, pane = pane
        new_objects = list(self.objects)
        new_objects[index] = panel(pane, name=name)
        self.objects = new_objects

    def append(self, pane):
        from .pane import panel
        name = None
        if isinstance(pane, tuple):
            name, pane = pane
        new_objects = list(self.objects)
        new_objects.append(panel(pane, name=name))
        self.objects = new_objects

    def insert(self, index, pane):
        from .pane import panel
        name = None
        if isinstance(pane, tuple):
            name, pane = pane
        new_objects = list(self.objects)
        new_objects.insert(index, panel(pane))
        self.objects = new_objects

    def pop(self, index):
        new_objects = list(self.objects)
        if index in new_objects:
            index = new_objects.index(index)
        new_objects.pop(index)
        self.objects = new_objects

    def _cleanup(self, model=None, final=False):
        super(Panel, self)._cleanup(model, final)
        if model is not None:
            for p, c in zip(self.objects, model.tabs):
                p._cleanup(c.child, final)


class Spacer(Reactive):
    """Empty object used to control formatting (using positive or negative space)"""
    
    height = param.Integer(default=None, bounds=(None, None))

    width = param.Integer(default=None, bounds=(None, None))

    _bokeh_model = BkSpacer

    def _init_properties(self):
        properties = {k: v for k, v in self.param.get_param_values()
                      if v not in [None, 'name']}
        return self._process_param_change(properties)

    def _get_model(self, doc, root=None, parent=None, comm=None):
        model = self._bokeh_model(**self._init_properties())
        self._link_params(model, ['width', 'height'], doc, root, comm)
        return model
