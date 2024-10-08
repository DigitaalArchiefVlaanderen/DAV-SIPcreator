from PySide6 import QtWidgets, QtCore, QtGui


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

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        title = QtWidgets.QLabel(text=title)
        title.setFont(font)
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

    def add_to_metadata(self, tags: list):
        self.metadata_mapping.clear_tags()
        self.metadata_mapping.add_tags(tags)

    def add_to_import_template(self, tags: list):
        self.import_mapping.clear_tags()
        self.import_mapping.add_tags(
            [t for t in tags if t not in ("Path in SIP", "Type", "DossierRef")]
        )

    def add_to_mapping(self, tags: list):
        self.output_mapping.add_tags(tags)

    # TODO: currently unused, but leaving it for now
    def fill_from_sip_widget(self, sip_widget):
        mapping = sip_widget.mapping
        self.add_to_mapping([f"{k} -> {v}" for k, v in mapping.items()])

        if sip_widget.metadata_df is not None:
            metadata_columns = sip_widget.metadata_df.columns
            self.add_to_metadata(
                [c for c in metadata_columns if c not in mapping.keys()]
            )

        import_template_columns = sip_widget.import_template_df.columns
        self.add_to_import_template(
            [c for c in import_template_columns if c not in mapping.values()]
        )

    def map_tags_clicked(self):
        selected_metadata_tag = self.metadata_mapping.get_selected_tag()
        selected_importsjabloon_tag = self.import_mapping.get_selected_tag()

        if selected_metadata_tag is None or selected_importsjabloon_tag is None:
            return

        self.output_mapping.add_tag(
            f"{selected_metadata_tag.text()} -> {selected_importsjabloon_tag.text()}"
        )

        self.metadata_mapping.remove_selected_tag()
        self.import_mapping.remove_selected_tag()

    def unmap_tags_clicked(self):
        selected_tag = self.output_mapping.get_selected_tag()

        if selected_tag is None:
            return

        metadata_tag, importsjabloon_tag = selected_tag.text().split(" -> ")

        self.metadata_mapping.add_tag(metadata_tag)
        self.import_mapping.add_tag(importsjabloon_tag)

        self.output_mapping.remove_selected_tag()

    def get_mapping(self):
        return {
            b.text().split(" -> ")[0]: b.text().split(" -> ")[1]
            for b in self.output_mapping.button_group.buttons()
        }


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
        # TODO: figure out how to give this as an option without it being weird
        # self.add_to_metadata(["<Dossiernaam>"])

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

    def get_mapping(self) -> list:
        return [b.text() for b in self.output_mapping.button_group.buttons()]
