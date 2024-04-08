from PySide6 import QtWidgets, QtCore

from .dialog import Dialog


class SearchableListWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.application = QtWidgets.QApplication.instance()

        grid_layout = QtWidgets.QGridLayout()
        grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(grid_layout)

        self.searchbox = QtWidgets.QLineEdit()
        self.searchbox.textEdited.connect(self.reload_widgets)
        grid_layout.addWidget(self.searchbox, 0, 0)

        self.count_label = QtWidgets.QLabel(text="0")
        grid_layout.addWidget(self.count_label, 0, 1)

        scroll_area = QtWidgets.QScrollArea()
        central_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout()
        self.list_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        central_widget.setLayout(self.list_layout)
        scroll_area.setWidget(central_widget)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        scroll_area.setWidgetResizable(True)
        grid_layout.addWidget(scroll_area, 1, 0, 1, 2)

        self.widgets = []

    # NOTE: not optimal to always do it all over, but shouldn't be too much of an issue
    def reload_widgets(self, *args):
        # Instead of deleting and adding items, we simply set their visibility
        widgets_to_show = self.search_widgets()

        for i in range(self.list_layout.count()):
            widget = self.list_layout.itemAt(i).widget()
            widget.setVisible(False)

            if widget in widgets_to_show:
                widget.setVisible(True)

    def get_widget_by_value(self, value: str):
        for w in self.widgets:
            if getattr(w["reference"], w["field"]) == value:
                return w

    # NOTE: we implemented our own search function here
    def search_widgets(self):
        partial_name = self.searchbox.text()

        if partial_name == "":
            return list(map(lambda w: w["reference"], self.widgets))

        widgets_to_show = []

        for widget in self.widgets:
            if partial_name in getattr(widget["reference"], widget["field"]):
                widgets_to_show.append(widget["reference"])

        return widgets_to_show

    def remove_widget_by_value(self, value: str):
        # We do not care if it's a widget we do not have
        if not (widget := self.get_widget_by_value(value)):
            return

        try:
            self.list_layout.removeWidget(widget["reference"])
            # Make sure we don't double delete
            widget["reference"].destroyed.disconnect()
            widget["reference"].deleteLater()
        except RuntimeError:
            # Item was already deleted somewhere else
            pass

        self.widgets.remove(widget)
        self.count_label.setText(str(len(self.widgets)))

    def add_item(self, searchable_name_field: str, widget: QtWidgets.QWidget) -> bool:
        # We want stuff to be unique, but will just overwrite if it isn't
        # TODO: proper logging
        if not hasattr(widget, searchable_name_field):
            return False

        value = getattr(widget, searchable_name_field)

        if self.get_widget_by_value(value):
            dialog = Dialog(
                title="Item bestaat al",
                text="Een item met dezelfde naam bestaat al. Wil je dit overschrijven?",
            )
            dialog.exec_()

            if not dialog.result():
                return False

            self.remove_widget_by_value(value)

        self.widgets.append(
            {
                "reference": widget,
                "field": searchable_name_field,
            }
        )
        self.list_layout.addWidget(widget)
        widget.destroyed.connect(lambda _: self.remove_widget_by_value(value))
        self.reload_widgets()
        self.count_label.setText(str(len(self.widgets)))

        return True


class SearchableSelectionListView(SearchableListWidget):
    def get_selected(self):
        selected_dossiers = []

        for i in range(self.list_layout.count()):
            dossier = self.list_layout.itemAt(i).widget()

            if dossier.is_selected():
                selected_dossiers.append(dossier)

        return selected_dossiers
