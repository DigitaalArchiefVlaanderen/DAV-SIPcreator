"""
Implementation of container widget.
It will vertically show component widgets provided dynamically.

A search bar will be provided to look for the elements based on a field given dynamically.

Note that the field must be a property, not a callable.
You are allowed to use dotnotation for deeper properties (eg: child.label.text)
"""
from typing import Any

from natsort import natsorted
from PySide6 import QtWidgets, QtCore

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.helper import get_attr_deep

from src.widget.base_widget import BaseWidget



class SearchableListWidget(BaseWidget):
    amount_changed_signal = QtCore.Signal()
    widgets_reloaded_signal = QtCore.Signal()

    def __init__(self, search_field: str):
        super().__init__()

        self.search_field = search_field

        self.widgets: list[BaseWidget] = []
        self.filtered_widgets: list[BaseWidget] = []

        self.widget_search_fields: list[Any] = []

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.grid_layout)

        # Searchbar
        self.searchbar = QtWidgets.QLineEdit()
        self.searchbar.editingFinished.connect(self.reload_shown_widgets)

        # Count label
        self.count_label = QtWidgets.QLabel(text="0/0")
        self.amount_changed_signal.connect(lambda: self.count_label.setText(f"{len(self.filtered_widgets)}/{len(self.widgets)}"))

        # Scroll area
        self.scroll_area = QtWidgets.QScrollArea()
        self.central_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout()
        self.list_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.central_widget.setLayout(self.list_layout)
        self.scroll_area.setWidget(self.central_widget)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scroll_area.setWidgetResizable(True)


        self.grid_layout.addWidget(self.searchbar, 0, 0)
        self.grid_layout.addWidget(self.count_label, 0, 1)
        self.grid_layout.addWidget(self.scroll_area, 1, 0, 1, 2)

    def search_for_widgets(self) -> None:
        """
        Search for widgets based on the provided filter and parameter to look for
        """
        search_text = self.searchbar.text()

        if search_text.strip() == "":
            self.filtered_widgets = self.widgets
            return

        self.filtered_widgets = [
            widget
            for widget in self.widgets
            if search_text in get_attr_deep(widget, self.search_field)
        ]

    def clear_widgets(self, delete: bool = False) -> None:
        for i in reversed(range(self.list_layout.count())):
            item = self.list_layout.itemAt(i)
            widget = item.widget()
            self.list_layout.removeItem(item)

            if delete and widget is not None:
                widget.hide()
                widget.deleteLater()

        if delete:
            self.widgets.clear()
            self.filtered_widgets.clear()

            self.amount_changed_signal.emit()

    def reload_shown_widgets(self, sort: bool=False) -> None:
        self.hide()
        self.search_for_widgets()

        if sort:
            self.widgets = natsorted(
                self.widgets, key=lambda w: get_attr_deep(w, self.search_field)
            )

            # Clear and read all the widgets to the layout
            self.clear_widgets()

            for widget in self.widgets:
                self.list_layout.addWidget(widget)

        for i in range(self.list_layout.count()):
            widget: BaseWidget = self.list_layout.itemAt(i).widget()

            if widget in self.filtered_widgets:
                widget.show()
            else:
                widget.hide()

        self.amount_changed_signal.emit()
        self.show()

        self.widgets_reloaded_signal.emit()

    def add_widgets(self, widgets: list[BaseWidget]) -> None:
        # NOTE: we only want to add widgets that we don't have yet
        widgets_to_add = [w for w in widgets if w not in self.widgets]

        self.widgets.extend(widgets_to_add)

        for widget in self.widgets:
            self.list_layout.addWidget(widget)

        self.reload_shown_widgets(sort=True)

    def remove_widgets(self, widgets: list[BaseWidget]) -> None:
        for widget in widgets:
            if widget.isHidden():
                return

            if widget not in self.widgets:
                print(self.widgets)
                return

            self.widgets.remove(widget)
            self.list_layout.removeWidget(widget)
            widget.hide()

        self.reload_shown_widgets()


class SearchableListWidgetWithSelection(BaseWidget):
    """
    Acts as a wrapper around the "parent" class
    Allowing us to add extra UI elements cleanly
    """
    selection_changed_signal = QtCore.Signal()

    class CheckBoxWidget(QtWidgets.QFrame):
        state_changed_signal = QtCore.Signal()

        def __init__(self, widget: BaseWidget):
            super().__init__()

            self.setFrameShape(QtWidgets.QFrame.Box)
            self.setLineWidth(1)

            self.horizontal_layout = QtWidgets.QHBoxLayout()
            self.horizontal_layout.setContentsMargins(10, 10, 10, 10)
            self.horizontal_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            self.setLayout(self.horizontal_layout)

            self.base_widget = widget

            self.checkbox = QtWidgets.QCheckBox()
            self.checkbox.stateChanged.connect(self.state_changed_signal)

            self.horizontal_layout.addWidget(self.checkbox)
            self.horizontal_layout.addWidget(widget)

        def mousePressEvent(self, event):
            if event.button() == QtCore.Qt.LeftButton:
                self.set_checked(not self.is_checked)

            super().mousePressEvent(event)

        @property
        def is_checked(self) -> bool:
            return self.checkbox.checkState() == QtCore.Qt.CheckState.Checked

        def set_checked(self, checked: bool) -> None:
            # NOTE: we do not want to trigger the signal here, since this happened automatically
            self.checkbox.setChecked(checked)

        def __eq__(self, other: "SearchableListWidgetWithSelection.CheckBoxWidget") -> bool:
            if not isinstance(other, SearchableListWidgetWithSelection.CheckBoxWidget):
                return False
            
            return self.base_widget == other.base_widget


    def __init__(self, search_field: str):
        super().__init__()

        self.searchable_list_widget = SearchableListWidget(search_field=f"base_widget.{search_field}")

        self.searchable_list_widget.amount_changed_signal.connect(self.selection_changed_signal.emit)
        self.selection_changed_signal.connect(self.selection_changed_handler)

    def setup_ui(self, select_all_text: str, remove_item_text: str) -> None:
        self.searchable_list_widget.setup_ui()

        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.select_all_checkbox = QtWidgets.QCheckBox(text=select_all_text)
        self.select_all_checkbox.stateChanged.connect(self.select_all_handler)

        self.remove_selected_items_button = QtWidgets.QPushButton(text=remove_item_text)
        self.remove_selected_items_button.setEnabled(False)
        self.remove_selected_items_button.clicked.connect(self.remove_selected_handler)

        self.grid_layout.addWidget(self.select_all_checkbox, 0, 0)
        self.grid_layout.addWidget(self.searchable_list_widget, 1, 0)
        self.grid_layout.addWidget(self.remove_selected_items_button, 2, 0)

    def add_widgets(self, widgets: list[BaseWidget], select: bool=True) -> None:
        widgets: list[SearchableListWidgetWithSelection.CheckBoxWidget] = [SearchableListWidgetWithSelection.CheckBoxWidget(widget) for widget in widgets]

        # NOTE: we also need to set some signals here
        for widget in widgets:
            if widget in self.widgets:
                continue

            if select:
                widget.set_checked(True)

            widget.state_changed_signal.connect(self.selection_changed_signal.emit)

        self.searchable_list_widget.add_widgets(widgets=widgets)

    # Helper functions
    def get_selected_items(self) -> list[BaseWidget]:
        self.filtered_widgets: list[SearchableListWidgetWithSelection.CheckBoxWidget]
        return [w.base_widget for w in self.filtered_widgets if w.is_checked]

    # Handlers
    def selection_changed_handler(self) -> None:
        # NOTE: enable or disable remove button based on if we have anything selected currently
        self.remove_selected_items_button.setEnabled(
            any(
                widget.is_checked
                for widget in self.filtered_widgets
            )
        )

        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setChecked(
            len(self.filtered_widgets) > 0
            and all(
                widget.is_checked
                for widget in self.filtered_widgets
            )
        )
        self.select_all_checkbox.blockSignals(False)

    def select_all_handler(self, check_state: QtCore.Qt.CheckState) -> None:
        should_be_checked = False
        
        if check_state == QtCore.Qt.CheckState.Checked.value:
            should_be_checked = True

        widget: SearchableListWidgetWithSelection.CheckBoxWidget
        for widget in self.searchable_list_widget.widgets:
            if not widget.isHidden():
                widget.set_checked(should_be_checked)

        self.selection_changed_signal.emit()

    def remove_selected_handler(self) -> None:
        selected_widgets: list[SearchableListWidgetWithSelection.CheckBoxWidget] = [widget for widget in self.widgets if widget.is_checked]

        self.searchable_list_widget.remove_widgets(selected_widgets)
        self.application.main_db_controller.delete_dossier_paths([w.base_widget.path for w in selected_widgets])

    # NOTE: any methods or attributes we have not overwritten, direct them to the "parent"
    def __getattr__(self, name: str):
        return getattr(self.searchable_list_widget, name)
    

class SearchableListWidgetWithDropdown(BaseWidget):
    """
    Acts as a wrapper around the "parent" class
    Allowing us to add extra UI elements cleanly
    """
    SHOW_ALL_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]["sip_list"]["show_all"]

    def __init__(self, search_field: str, dropdown_search_field: str):
        super().__init__()

        self.searchable_list_widget = SearchableListWidget(search_field=search_field)
        self.searchable_list_widget.search_for_widgets = self.search_for_widgets

        self.dropdown_search_field = dropdown_search_field

    def setup_ui(self, dropdown_options: list) -> None:
        self.searchable_list_widget.setup_ui()

        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.dropdown = QtWidgets.QComboBox()
        self.dropdown.addItems([self.SHOW_ALL_TEXT] + dropdown_options)
        self.dropdown.currentTextChanged.connect(self.dropdown_text_changed_handler)

        self.grid_layout.addWidget(self.dropdown, 0, 0)
        self.grid_layout.addWidget(self.searchable_list_widget, 1, 0)

    def search_for_widgets(self) -> None:
        """
        Search for widgets based on the provided filter from the dropdown.
        Combined with the search in the text
        """
        # Search based on text
        search_text = self.searchbar.text()

        if search_text.strip() == "":
            self.searchable_list_widget.filtered_widgets = self.widgets
        else:
            self.searchable_list_widget.filtered_widgets = [
                widget
                for widget in self.widgets
                if search_text in get_attr_deep(widget, self.search_field)
            ]

        # Search based on dropdown (refine the previous search)
        if (current_text := self.dropdown.currentText()) == self.SHOW_ALL_TEXT:
            return

        # Filter down even more
        self.searchable_list_widget.filtered_widgets = [
            widget
            for widget in self.filtered_widgets
            if current_text == get_attr_deep(widget, self.dropdown_search_field)
        ]


    # Handlers
    def dropdown_text_changed_handler(self) -> None:
        self.searchable_list_widget.reload_shown_widgets()

        
    # NOTE: any methods or attributes we have not overwritten, direct them to the "parent"
    def __getattr__(self, name: str):
        return getattr(self.searchable_list_widget, name)
