# Script Version: 0.4.3 | Phase 5: Polish & Depth Control
# Description: Updated parameter ranges (0-999 for global limit, 0-63 for others).

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, 
    QLabel, QLineEdit, QPushButton, QFormLayout, QSpinBox, 
    QDoubleSpinBox, QComboBox, QTextEdit, QListWidget, QMessageBox,
    QGroupBox
)
from PyQt6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, settings_manager, model_manager, prompt_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gauntlet Settings")
        self.resize(800, 600)
        
        self.settings_mgr = settings_manager
        self.model_mgr = model_manager
        self.prompt_mgr = prompt_manager
        
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tab_general = QWidget()
        self._init_general_tab()
        self.tabs.addTab(self.tab_general, "General & API")

        self.tab_roles = QWidget()
        self._init_roles_tab()
        self.tabs.addTab(self.tab_roles, "Roles")

        self.tab_models = QWidget()
        self._init_models_tab()
        self.tabs.addTab(self.tab_models, "Models")

        self.tab_params = QWidget()
        self._init_params_tab()
        self.tabs.addTab(self.tab_params, "Parameters")

        self.tab_prompts = QWidget()
        self._init_prompts_tab()
        self.tabs.addTab(self.tab_prompts, "Prompts")

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save All Changes")
        save_btn.clicked.connect(self._save_all)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _init_general_tab(self):
        layout = QFormLayout(self.tab_general)
        
        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-or-...")
        layout.addRow("OpenRouter API Key:", self.api_key_input)
        
        lbl = QLabel("Note: API Key is stored in .env file locally.")
        lbl.setStyleSheet("color: gray; font-style: italic;")
        layout.addRow("", lbl)

        # Font Size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        self.font_size_spin.setSuffix(" pt")
        layout.addRow("Global Font Size:", self.font_size_spin)

    def _init_roles_tab(self):
        layout = QVBoxLayout(self.tab_roles)
        self.role_widgets = {}
        roles = ["architect", "researcher", "auditor", "writer"]
        for role in roles:
            group = QGroupBox(role.capitalize())
            form = QFormLayout()
            model_combo = QComboBox()
            temp_spin = QDoubleSpinBox()
            temp_spin.setRange(0.0, 1.0)
            temp_spin.setSingleStep(0.1)
            form.addRow("Model:", model_combo)
            form.addRow("Temperature:", temp_spin)
            group.setLayout(form)
            layout.addWidget(group)
            self.role_widgets[role] = {"combo": model_combo, "temp": temp_spin}

    def _init_models_tab(self):
        layout = QVBoxLayout(self.tab_models)
        self.model_list = QListWidget()
        layout.addWidget(self.model_list)
        form_layout = QHBoxLayout()
        self.new_model_name = QLineEdit()
        self.new_model_name.setPlaceholderText("Model Name")
        self.new_model_id = QLineEdit()
        self.new_model_id.setPlaceholderText("Model ID")
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_model)
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._del_model)
        form_layout.addWidget(self.new_model_name)
        form_layout.addWidget(self.new_model_id)
        form_layout.addWidget(add_btn)
        layout.addLayout(form_layout)
        layout.addWidget(del_btn)

    def _init_params_tab(self):
        layout = QFormLayout(self.tab_params)
        self.params_widgets = {}
        
        params = [
            ("max_iterations", "Global Safety Limit (Total Steps)", int),
            ("max_gap_iterations", "Max Gap Resolution Rounds", int),
            ("max_gaps_allowed", "Max Allowable Gaps (Goal)", int),
            ("initial_search_depth", "Initial Search Depth (Iter 0)", int),
            ("refinement_search_depth", "Refinement Search Depth (Iter > 0)", int),
            ("search_queries_per_question", "Queries per Question", int),
            ("search_results_per_query", "Results per Query", int),
            ("academic_papers_per_query", "Academic Papers per Query", int),
            ("min_quality_score", "Min Quality Score (0.0-1.0)", float)
        ]
        
        for key, label, dtype in params:
            if dtype == int:
                widget = QSpinBox()
                if key == "max_iterations":
                    widget.setRange(0, 999)
                else:
                    widget.setRange(0, 63)
            else:
                widget = QDoubleSpinBox()
                widget.setRange(0.0, 1.0)
                widget.setSingleStep(0.05)
            
            layout.addRow(label, widget)
            self.params_widgets[key] = widget

    def _init_prompts_tab(self):
        layout = QVBoxLayout(self.tab_prompts)
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Select Prompt:"))
        self.prompt_selector = QComboBox()
        self.prompt_selector.currentIndexChanged.connect(self._load_selected_prompt)
        top_row.addWidget(self.prompt_selector)
        layout.addLayout(top_row)
        layout.addWidget(QLabel("System Prompt:"))
        self.system_edit = QTextEdit()
        self.system_edit.setMaximumHeight(100)
        layout.addWidget(self.system_edit)
        layout.addWidget(QLabel("User Template:"))
        self.user_edit = QTextEdit()
        layout.addWidget(self.user_edit)

    def _load_data(self):
        # General
        self.api_key_input.setText(os.getenv("OPENROUTER_API_KEY", ""))
        self.font_size_spin.setValue(self.settings_mgr.get("font_size", 14))
        
        # Models
        self.model_list.clear()
        self.available_models = self.model_mgr.get_all()
        for m in self.available_models:
            self.model_list.addItem(f"{m['name']} ({m['id']})")
            
        # Roles
        for role, widgets in self.role_widgets.items():
            widgets["combo"].clear()
            for m in self.available_models:
                widgets["combo"].addItem(m['name'], m['id'])
            role_data = self.settings_mgr.get_role(role)
            idx = widgets["combo"].findData(role_data.get("model_id"))
            if idx >= 0: widgets["combo"].setCurrentIndex(idx)
            widgets["temp"].setValue(role_data.get("temperature", 0.2))

        # Params
        for key, widget in self.params_widgets.items():
            val = self.settings_mgr.get_param(key)
            if val is not None:
                widget.setValue(val)

        # Prompts
        self.prompt_selector.clear()
        self.prompts_data = self.prompt_mgr.prompts
        for key in self.prompts_data.keys():
            self.prompt_selector.addItem(key)
        self._load_selected_prompt()

    def _load_selected_prompt(self):
        key = self.prompt_selector.currentText()
        if not key: return
        data = self.prompts_data.get(key, {})
        self.system_edit.setText(data.get("system", ""))
        self.user_edit.setText(data.get("user_template", ""))

    def _add_model(self):
        name = self.new_model_name.text().strip()
        mid = self.new_model_id.text().strip()
        if name and mid:
            if self.model_mgr.add_model(name, mid):
                self._load_data()
                self.new_model_name.clear()
                self.new_model_id.clear()
            else:
                QMessageBox.warning(self, "Error", "Model ID already exists.")

    def _del_model(self):
        row = self.model_list.currentRow()
        if row >= 0:
            text = self.model_list.item(row).text()
            mid = text.split("(")[-1].strip(")")
            self.model_mgr.delete_model(mid)
            self._load_data()

    def _save_all(self):
        # General
        key = self.api_key_input.text().strip()
        if key:
            self._update_env("OPENROUTER_API_KEY", key)
            os.environ["OPENROUTER_API_KEY"] = key
        
        self.settings_mgr.set("font_size", self.font_size_spin.value())

        # Roles
        for role, widgets in self.role_widgets.items():
            mid = widgets["combo"].currentData()
            temp = widgets["temp"].value()
            self.settings_mgr.set_role(role, mid, temp)

        # Params
        for key, widget in self.params_widgets.items():
            self.settings_mgr.set_param(key, widget.value())

        # Prompts
        curr_key = self.prompt_selector.currentText()
        if curr_key:
            self.prompt_mgr.set(curr_key, self.system_edit.toPlainText(), self.user_edit.toPlainText())
        
        QMessageBox.information(self, "Saved", "Settings saved successfully.")
        self.accept()

    def _update_env(self, key, value):
        lines = []
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                lines = f.readlines()
        found = False
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith(f"{key}="):
                    f.write(f'{key}="{value}"\n')
                    found = True
                else:
                    f.write(line)
            if not found:
                f.write(f'{key}="{value}"\n')
