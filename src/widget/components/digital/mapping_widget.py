from PySide6 import QtCore, QtWidgets

from src.utils.constants import ColumnName
from src.utils.pyside_helper import make_listitem_title_font


class TagWidget(QtWidgets.QFrame):
    def __init__(self, button_group: QtWidgets.QButtonGroup, tag: str):
        super().__init__()

        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)

        self.radio_button = QtWidgets.QRadioButton(parent=self, text=tag)
        button_group.addButton(self.radio_button)
        self.horizontal_layout.addWidget(self.radio_button)


class TagListWidget(QtWidgets.QScrollArea):
    def __init__(self, parent, title: str):
        super().__init__(parent=parent)

        central_widget = QtWidgets.QWidget()
        self.vertical_layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(self.vertical_layout)
        self.setWidget(central_widget)

        title = QtWidgets.QLabel(text=title)
        title.setFont(make_listitem_title_font())
        self.vertical_layout.addWidget(title)

        self.button_group = QtWidgets.QButtonGroup()

        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)
        self.vertical_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    def add_tag(self, tag: str):
        self.vertical_layout.addWidget(TagWidget(self.button_group, tag))

    def clear_tags(self):
        for i in range(1, self.vertical_layout.count()):
            widget = self.vertical_layout.itemAt(i).widget()
            widget.deleteLater()

    def add_tags(self, tags: str):
        for tag in tags:
            self.add_tag(tag)

    def get_selected_tag(self):
        return self.button_group.checkedButton()

    def remove_selected_tag(self):
        self.get_selected_tag().parent().deleteLater()


# NOTE: just taken from old code, might need some fixes or cleanup
class TagMappingWidget(QtWidgets.QFrame):
    class MappingButtonWidget(QtWidgets.QWidget):
        def __init__(self, map_tags_callback, unmap_tags_callback):
            super().__init__()

            self.vertical_layout = QtWidgets.QVBoxLayout()
            self.setLayout(self.vertical_layout)

            self.map_tags_button = QtWidgets.QPushButton(text=">>>")
            self.map_tags_button.clicked.connect(map_tags_callback)
            self.vertical_layout.addWidget(self.map_tags_button)

            self.unmap_tags_button = QtWidgets.QPushButton(text="<<<")
            self.unmap_tags_button.clicked.connect(unmap_tags_callback)
            self.vertical_layout.addWidget(self.unmap_tags_button)

    def __init__(self):
        super().__init__()

        self._import_usage_slots: dict[str, set[int]] = {}
        self._display_to_actual: dict[int, str] = {}

        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)

        self.metadata_mapping = TagListWidget(self, title="Metadata")
        self.horizontal_layout.addWidget(self.metadata_mapping)

        self.import_mapping = TagListWidget(self, title="Importsjabloon")
        self.horizontal_layout.addWidget(self.import_mapping)

        self.mapping_buttons = TagMappingWidget.MappingButtonWidget(
            map_tags_callback=self.map_tags_clicked,
            unmap_tags_callback=self.unmap_tags_clicked,
        )
        self.horizontal_layout.addWidget(self.mapping_buttons)

        self.output_mapping = TagListWidget(self, title="Mapping")
        self.horizontal_layout.addWidget(self.output_mapping)

    def _reset_mapping_state(self):
        self._import_usage_slots.clear()
        self._display_to_actual.clear()
        self.output_mapping.clear_tags()

    def add_to_metadata(self, tags: list):
        self._reset_mapping_state()
        self.metadata_mapping.clear_tags()
        self.metadata_mapping.add_tags(tags)

    def add_to_import_template(self, tags: list):
        self._reset_mapping_state()
        self.import_mapping.clear_tags()
        self.import_mapping.add_tags(
            [t for t in tags if t not in (ColumnName.TYPE, ColumnName.DOSSIER_REF, ColumnName.ANALOOG)]
        )

    def add_to_mapping(self, tags: list):
        self.output_mapping.add_tags(tags)

    def _next_slot(self, base_name: str) -> int:
        used = self._import_usage_slots.get(base_name, set())
        slot = 0
        while slot in used:
            slot += 1
        return slot

    def map_tags_clicked(self):
        selected_metadata_tag = self.metadata_mapping.get_selected_tag()
        selected_importsjabloon_tag = self.import_mapping.get_selected_tag()

        if selected_metadata_tag is None or selected_importsjabloon_tag is None:
            return

        base_name = selected_importsjabloon_tag.text()

        slot = self._next_slot(base_name)
        effective_name = base_name + " " * slot

        self._import_usage_slots.setdefault(base_name, set()).add(slot)

        self.output_mapping.add_tag(f"{selected_metadata_tag.text()} -> {base_name}")

        button = self.output_mapping.button_group.buttons()[-1]
        btn_id = self.output_mapping.button_group.id(button)
        self._display_to_actual[btn_id] = effective_name

        self.metadata_mapping.remove_selected_tag()

        # Path in SIP is a linking column — remove from import list so only one mapping is possible
        if base_name == ColumnName.PATH_IN_SIP:
            self.import_mapping.remove_selected_tag()

    def unmap_tags_clicked(self):
        selected_tag = self.output_mapping.get_selected_tag()

        if selected_tag is None:
            return

        metadata_tag, _ = selected_tag.text().split(" -> ", 1)

        btn_id = self.output_mapping.button_group.id(selected_tag)
        actual_import = self._display_to_actual.pop(btn_id, "")
        base_name = actual_import.rstrip()
        slot = len(actual_import) - len(base_name)

        if base_name in self._import_usage_slots:
            self._import_usage_slots[base_name].discard(slot)
            if not self._import_usage_slots[base_name]:
                del self._import_usage_slots[base_name]

        self.metadata_mapping.add_tag(metadata_tag)

        # Re-add Path in SIP to the import list when unmapped
        if base_name == ColumnName.PATH_IN_SIP:
            self.import_mapping.add_tag(base_name)

        self.output_mapping.remove_selected_tag()

    def is_valid_mapping(self) -> bool:
        """A mapping is valid if it's empty or includes Path in SIP."""
        mapping = self.get_mapping()
        if not mapping:
            return True
        return any(imp.rstrip() == ColumnName.PATH_IN_SIP for _, imp in mapping)

    def get_mapping(self) -> list[tuple[str, str]]:
        return [
            (b.text().split(" -> ", 1)[0], self._display_to_actual[self.output_mapping.button_group.id(b)])
            for b in self.output_mapping.button_group.buttons()
        ]


class FolderMappingWidget(QtWidgets.QFrame):
    class MappingButtonWidget(QtWidgets.QWidget):
        def __init__(self, map_tags_callback, unmap_tags_callback):
            super().__init__()

            self.vertical_layout = QtWidgets.QVBoxLayout()
            self.setLayout(self.vertical_layout)

            self.map_tags_button = QtWidgets.QPushButton(text=">>>")
            self.map_tags_button.clicked.connect(map_tags_callback)
            self.vertical_layout.addWidget(self.map_tags_button)

            self.unmap_tags_button = QtWidgets.QPushButton(text="<<<")
            self.unmap_tags_button.clicked.connect(unmap_tags_callback)
            self.vertical_layout.addWidget(self.unmap_tags_button)

    def __init__(self):
        super().__init__()

        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        self.metadata_mapping = TagListWidget(self, title="Metadata")

        mapping_buttons = TagMappingWidget.MappingButtonWidget(
            map_tags_callback=self.map_tags_clicked,
            unmap_tags_callback=self.unmap_tags_clicked,
        )

        self.output_mapping = TagListWidget(self, title="Mapping")

        self.save_button = QtWidgets.QPushButton(text="Opslaan")

        grid_layout.addWidget(self.metadata_mapping, 1, 0)
        grid_layout.addWidget(mapping_buttons, 1, 1)
        grid_layout.addWidget(self.output_mapping, 1, 2)
        grid_layout.addWidget(self.save_button, 2, 0, 1, 3)

    def add_to_metadata(self, tags: list):
        self.metadata_mapping.add_tags(tags)

    def map_tags_clicked(self):
        selected_metadata_tag = self.metadata_mapping.get_selected_tag()

        if selected_metadata_tag is None:
            return

        self.output_mapping.add_tag(selected_metadata_tag.text())
        self.metadata_mapping.remove_selected_tag()

    def unmap_tags_clicked(self):
        selected_tag = self.output_mapping.get_selected_tag()

        if selected_tag is None:
            return

        self.metadata_mapping.add_tag(selected_tag.text())
        self.output_mapping.remove_selected_tag()

    def get_mapping(self) -> list[str]:
        return [b.text() for b in self.output_mapping.button_group.buttons()]
