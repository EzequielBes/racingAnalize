"""
Widget de gerenciamento de setups para o Race Telemetry Analyzer.
Permite gerenciar, comparar e aplicar setups de carros.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QSplitter, QFrame, QGroupBox, QGridLayout,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox,
    QSlider, QFileDialog, QMessageBox, QDialog, QFormLayout
)
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QSize
from typing import Dict, List, Any, Optional

import os
import json
import shutil
import logging
from datetime import datetime

# Configuração de logging
logger = logging.getLogger("race_telemetry_api.setup")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)


class SetupCard(QFrame):
    """Widget de card para exibir um setup."""
    
    setup_selected = pyqtSignal(dict)
    setup_exported = pyqtSignal(dict, str) # Emite dados e caminho para o widget pai tratar
    setup_edited = pyqtSignal(dict) # Emite dados atualizados após edição
    
    def __init__(self, setup_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setMinimumHeight(150)
        self.setMinimumWidth(250)
        self.setup_data = setup_data
        
        layout = QVBoxLayout(self)
        car_label = QLabel(setup_data.get("car", "Desconhecido"))
        car_label.setObjectName("card-title")
        font = car_label.font()
        font.setBold(True)
        car_label.setFont(font)
        layout.addWidget(car_label)
        
        # CORRIGIDO: Usar aspas simples dentro da f-string
        layout.addWidget(QLabel(f"Pista: {setup_data.get('track', 'Desconhecida')}"))
        layout.addWidget(QLabel(f"Autor: {setup_data.get('author', 'Desconhecido')}"))
        
        date_str = setup_data.get("date", "")
        if isinstance(date_str, str) and date_str:
            try:
                date = datetime.fromisoformat(date_str)
                date_str = date.strftime("%d/%m/%Y")
            except ValueError:
                pass # Mantém a string original se não for ISO
        layout.addWidget(QLabel(f"Data: {date_str}"))
        
        buttons_layout = QHBoxLayout()
        self.view_button = QPushButton("Ver")
        self.edit_button = QPushButton("Editar")
        self.export_button = QPushButton("Exportar")
        buttons_layout.addWidget(self.view_button)
        buttons_layout.addWidget(self.edit_button)
        buttons_layout.addWidget(self.export_button)
        layout.addLayout(buttons_layout)
        
        self.view_button.clicked.connect(self._on_view_clicked)
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.export_button.clicked.connect(self._on_export_clicked)
    
    def _on_view_clicked(self):
        self.setup_selected.emit(self.setup_data)
    
    def _on_edit_clicked(self):
        dialog = SetupEditDialog(self.setup_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_setup_data()
            # Atualiza os dados internos do card também
            self.setup_data = updated_data 
            # Atualiza a exibição do card (ex: título, data)
            self._update_display()
            # Emite o sinal para o widget pai salvar/atualizar
            self.setup_edited.emit(updated_data)
            logger.info(f"Setup editado: {updated_data.get('id')}")

    def _update_display(self):
         # Atualiza os labels do card com os novos dados
         # (Implementação simplificada, assume que os widgets são acessíveis)
         try:
             self.findChild(QLabel, "card-title").setText(self.setup_data.get("car", "Desconhecido"))
             # Atualizar outros labels se necessário...
         except AttributeError:
             logger.warning("Não foi possível atualizar a exibição do card após edição.")

    def _on_export_clicked(self):
        # Pede apenas o caminho ao usuário
        file_dialog = QFileDialog()
        default_filename = f"{self.setup_data.get('car', 'setup').replace(' ', '_')}_{self.setup_data.get('track', 'track').replace(' ', '_')}.json"
        # Sugere o diretório padrão de setups
        setups_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer", "setups")
        default_path = os.path.join(setups_dir, default_filename)
        
        file_path, _ = file_dialog.getSaveFileName(
            self,
            "Exportar Setup",
            default_path, # Diretório e nome sugeridos
            "Arquivos JSON (*.json);;Todos os Arquivos (*)"
        )
        
        if file_path:
            # Emite o sinal com os dados e o caminho escolhido
            # O widget pai será responsável por criar o diretório e salvar
            self.setup_exported.emit(self.setup_data, file_path)


class SetupDetailPanel(QFrame):
    """Painel para exibir detalhes de um setup."""
    
    export_requested = pyqtSignal(dict, str) # Emite dados e caminho para o widget pai tratar
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Detalhes do Setup")
        self.title_label.setObjectName("section-title")
        layout.addWidget(self.title_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        self.detail_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        buttons_layout = QHBoxLayout()
        self.apply_button = QPushButton("Aplicar Setup (Manual)")
        self.export_button = QPushButton("Exportar Setup")
        # self.share_button = QPushButton("Compartilhar") # Funcionalidade futura
        buttons_layout.addWidget(self.apply_button)
        buttons_layout.addWidget(self.export_button)
        # buttons_layout.addWidget(self.share_button)
        layout.addLayout(buttons_layout)
        
        self.export_button.clicked.connect(self._on_export_clicked)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        # self.share_button.clicked.connect(self._on_share_clicked)
        
        self.current_setup = None
    
    def update_setup_details(self, setup_data: Dict[str, Any]):
        self.current_setup = setup_data
        car = setup_data.get("car", "Desconhecido")
        track = setup_data.get("track", "Desconhecida")
        self.title_label.setText(f"Setup: {car} - {track}")
        
        # Limpa layout anterior
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Adiciona grupos de informações (simplificado para brevidade)
        self._add_detail_group("Informações Básicas", {
            "Carro": setup_data.get("car", "--"),
            "Pista": setup_data.get("track", "--"),
            "Autor": setup_data.get("author", "--"),
            "Data": self._format_date(setup_data.get("date"))
        })
        
        if "suspension" in setup_data: self._add_detail_group("Suspensão", setup_data["suspension"])
        if "aero" in setup_data: self._add_detail_group("Aerodinâmica", setup_data["aero"])
        if "transmission" in setup_data: self._add_detail_group("Transmissão", setup_data["transmission"])
        if "tyres" in setup_data: self._add_detail_group("Pneus", setup_data["tyres"])
        
        if "notes" in setup_data and setup_data["notes"]:
            notes_group = QGroupBox("Notas")
            notes_layout = QVBoxLayout(notes_group)
            notes_text = QTextEdit(setup_data["notes"])
            notes_text.setReadOnly(True)
            notes_layout.addWidget(notes_text)
            self.detail_layout.addWidget(notes_group)
            
        self.detail_layout.addStretch()

    def _add_detail_group(self, title: str, data: Dict):
        """Adiciona um grupo de detalhes ao layout."""
        if not data: return
        group = QGroupBox(title)
        layout = QGridLayout(group)
        row = 0
        for key, value in data.items():
            layout.addWidget(QLabel(f"{key}:"), row, 0)
            layout.addWidget(QLabel(str(value)), row, 1)
            row += 1
        self.detail_layout.addWidget(group)

    def _format_date(self, date_str: Optional[str]) -> str:
        """Formata a string de data ISO para DD/MM/YYYY."""
        if not date_str:
            return "--"
        try:
            return datetime.fromisoformat(date_str).strftime("%d/%m/%Y")
        except (TypeError, ValueError):
            return date_str # Retorna original se não for formato esperado

    def _on_export_clicked(self):
        if not self.current_setup:
            return
        
        file_dialog = QFileDialog()
        default_filename = f"{self.current_setup.get('car', 'setup').replace(' ', '_')}_{self.current_setup.get('track', 'track').replace(' ', '_')}.json"
        setups_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer", "setups")
        default_path = os.path.join(setups_dir, default_filename)

        file_path, _ = file_dialog.getSaveFileName(
            self,
            "Exportar Setup",
            default_path,
            "Arquivos JSON (*.json);;Todos os Arquivos (*)"
        )
        
        if file_path:
            # Emite sinal para o widget pai tratar o salvamento
            self.export_requested.emit(self.current_setup, file_path)
    
    def _on_apply_clicked(self):
        QMessageBox.information(
            self,
            "Aplicar Setup",
            "A aplicação automática de setups ainda não está implementada.\n\n"
            "Por favor, ajuste manualmente os valores no simulador."
        )
    
    # def _on_share_clicked(self): ... # Implementação futura


class SetupEditDialog(QDialog):
    """Diálogo para edição/criação de setup."""
    
    def __init__(self, setup_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        
        self.is_new_setup = setup_data is None
        self.setup_data = setup_data.copy() if setup_data else {}
        
        self.setWindowTitle("Novo Setup" if self.is_new_setup else "Editar Setup")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Abas de Edição --- 
        # (Assume que as abas são criadas com QFormLayout e campos QLineEdit/QTextEdit)
        # Exemplo: Informações Básicas
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        self.car_edit = QLineEdit(self.setup_data.get("car", ""))
        self.track_edit = QLineEdit(self.setup_data.get("track", ""))
        self.author_edit = QLineEdit(self.setup_data.get("author", ""))
        basic_layout.addRow("Carro (*):", self.car_edit)
        basic_layout.addRow("Pista (*):", self.track_edit)
        basic_layout.addRow("Autor:", self.author_edit)
        tabs.addTab(basic_tab, "Informações Básicas")

        # Exemplo: Notas
        notes_tab = QWidget()
        notes_layout = QVBoxLayout(notes_tab)
        self.notes_edit = QTextEdit(self.setup_data.get("notes", ""))
        notes_layout.addWidget(QLabel("Notas Adicionais:"))
        notes_layout.addWidget(self.notes_edit)
        tabs.addTab(notes_tab, "Notas")
        
        # TODO: Adicionar abas para Suspensão, Aero, Transmissão, Pneus
        # com campos apropriados (QLineEdit, QSpinBox, etc.)
        # Armazenar referências aos campos em dicionários como self.suspension_fields

        # --- Botões --- 
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)
        
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def accept(self):
        """Valida e coleta os dados antes de fechar."""
        # Validação básica
        if not self.car_edit.text() or not self.track_edit.text():
            QMessageBox.warning(self, "Campos Obrigatórios", "Os campos 'Carro' e 'Pista' são obrigatórios.")
            return
            
        # Coleta dados básicos
        self.setup_data["car"] = self.car_edit.text()
        self.setup_data["track"] = self.track_edit.text()
        self.setup_data["author"] = self.author_edit.text()
        self.setup_data["notes"] = self.notes_edit.toPlainText()
        
        # Atualiza data se for novo ou editado
        self.setup_data["date"] = datetime.now().isoformat()
        
        # Gera ID se for novo setup
        if self.is_new_setup:
             timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
             self.setup_data["id"] = f"setup_{timestamp}"
        
        # TODO: Coletar dados das outras abas (Suspensão, Aero, etc.)
        # Exemplo: 
        # if hasattr(self, "suspension_fields"):
        #     self.setup_data["suspension"] = {k: v.text() for k, v in self.suspension_fields.items()}

        super().accept() # Fecha o diálogo com sucesso

    def get_setup_data(self) -> Dict[str, Any]:
        """Retorna os dados do setup coletados."""
        return self.setup_data


class SetupWidget(QWidget):
    """Widget principal para gerenciamento de setups."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Diretório padrão para setups
        self.setups_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer", "setups")
        os.makedirs(self.setups_dir, exist_ok=True) # Garante que o diretório exista
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # --- Barra de Ferramentas --- 
        toolbar_layout = QHBoxLayout()
        self.new_setup_button = QPushButton("Novo Setup")
        self.import_setup_button = QPushButton("Importar Setup")
        toolbar_layout.addWidget(self.new_setup_button)
        toolbar_layout.addWidget(self.import_setup_button)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)
        
        # --- Splitter Principal --- 
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # --- Painel Esquerdo (Lista de Setups) --- 
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(300)
        
        # Filtros (exemplo)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtrar por Carro:"))
        self.car_filter_combo = QComboBox()
        filter_layout.addWidget(self.car_filter_combo)
        left_layout.addLayout(filter_layout)
        # TODO: Adicionar filtro por pista e botão de aplicar filtro
        
        # Área de scroll para os cards
        scroll_area_cards = QScrollArea()
        scroll_area_cards.setWidgetResizable(True)
        scroll_area_cards.setFrameShape(QFrame.Shape.NoFrame)
        
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll_area_cards.setWidget(self.cards_widget)
        left_layout.addWidget(scroll_area_cards)
        
        splitter.addWidget(left_panel)
        
        # --- Painel Direito (Detalhes do Setup) --- 
        self.detail_panel = SetupDetailPanel()
        splitter.addWidget(self.detail_panel)
        
        # Conexões
        self.new_setup_button.clicked.connect(self.create_new_setup)
        self.import_setup_button.clicked.connect(self.import_setup_file)
        self.detail_panel.export_requested.connect(self.save_setup_to_file)
        
        # Carrega setups existentes
        self.load_setups()

    def load_setups(self):
        """Carrega setups do diretório padrão e atualiza a lista de cards."""
        logger.info(f"Carregando setups de: {self.setups_dir}")
        # Limpa cards existentes
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        cars = set()
        tracks = set()
        
        for filename in os.listdir(self.setups_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.setups_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        setup_data = json.load(f)
                        # Adiciona ID se não existir (para compatibilidade)
                        if "id" not in setup_data:
                            setup_data["id"] = filename.replace(".json", "")
                        
                        self.add_setup_card(setup_data)
                        cars.add(setup_data.get("car", "Desconhecido"))
                        tracks.add(setup_data.get("track", "Desconhecida"))
                except json.JSONDecodeError:
                    logger.error(f"Erro ao decodificar JSON: {file_path}")
                except Exception as e:
                    logger.error(f"Erro ao carregar setup {file_path}: {e}")
        
        # Atualiza filtros (exemplo)
        self.car_filter_combo.clear()
        self.car_filter_combo.addItem("Todos")
        self.car_filter_combo.addItems(sorted(list(cars)))
        # TODO: Atualizar filtro de pista
        
        logger.info(f"{self.cards_layout.count()} setups carregados.")

    def add_setup_card(self, setup_data: Dict[str, Any]):
        """Adiciona um card de setup ao layout."""
        card = SetupCard(setup_data)
        card.setup_selected.connect(self.detail_panel.update_setup_details)
        card.setup_exported.connect(self.save_setup_to_file)
        card.setup_edited.connect(self.save_setup_to_file) # Salva automaticamente após editar
        self.cards_layout.addWidget(card)

    def create_new_setup(self):
        """Abre o diálogo para criar um novo setup."""
        dialog = SetupEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_setup_data = dialog.get_setup_data()
            self.save_setup_to_file(new_setup_data)
            self.add_setup_card(new_setup_data) # Adiciona o novo card à lista
            logger.info(f"Novo setup criado e salvo: {new_setup_data.get('id')}")

    def import_setup_file(self):
        """Abre um diálogo para importar um arquivo de setup JSON."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Setup",
            self.setups_dir, # Começa no diretório padrão
            "Arquivos JSON (*.json);;Todos os Arquivos (*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_data = json.load(f)
            
            # Validação básica (pode ser mais robusta)
            if not isinstance(imported_data, dict) or "car" not in imported_data or "track" not in imported_data:
                raise ValueError("Formato de setup inválido.")
            
            # Gera ID se não existir
            if "id" not in imported_data:
                 timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                 imported_data["id"] = f"imported_{timestamp}"
            
            # Salva o setup importado no diretório padrão
            self.save_setup_to_file(imported_data)
            self.add_setup_card(imported_data) # Adiciona à lista
            QMessageBox.information(self, "Importação Concluída", f"Setup importado com sucesso de:\n{os.path.basename(file_path)}")
            logger.info(f"Setup importado: {imported_data.get('id')}")
            
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Erro de Importação", "O arquivo selecionado não é um JSON válido.")
            logger.error(f"Erro ao decodificar JSON importado: {file_path}")
        except ValueError as e:
            QMessageBox.critical(self, "Erro de Importação", f"Erro no formato do arquivo de setup:\n{e}")
            logger.error(f"Erro de formato ao importar setup: {file_path}, {e}")
        except Exception as e:
            QMessageBox.critical(self, "Erro de Importação", f"Ocorreu um erro inesperado ao importar o setup:\n{e}")
            logger.exception(f"Erro inesperado ao importar setup: {file_path}")

    @pyqtSlot(dict, str)
    def save_setup_to_file(self, setup_data: Dict[str, Any], file_path: Optional[str] = None):
        """Salva os dados do setup em um arquivo JSON."""
        if not file_path:
            # Se nenhum caminho for fornecido (ex: após edição), usa o ID para salvar no diretório padrão
            setup_id = setup_data.get("id")
            if not setup_id:
                logger.error("Não foi possível salvar o setup: ID ausente.")
                QMessageBox.critical(self, "Erro ao Salvar", "Não foi possível salvar o setup editado (ID ausente).")
                return
            file_path = os.path.join(self.setups_dir, f"{setup_id}.json")
        
        try:
            # Garante que o diretório de destino exista (caso seja exportação para outro local)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(setup_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Setup salvo com sucesso em: {file_path}")
            # Se foi uma exportação (caminho explícito), informa o usuário
            if file_path != os.path.join(self.setups_dir, f"{setup_data.get('id')}.json"):
                 QMessageBox.information(self, "Exportação Concluída", f"Setup exportado para:\n{file_path}")
        except Exception as e:
            logger.exception(f"Erro ao salvar setup em {file_path}: {e}")
            QMessageBox.critical(self, "Erro ao Salvar/Exportar", f"Não foi possível salvar o setup:\n{e}")

# Exemplo de uso (para teste)
if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    widget = SetupWidget()
    widget.show()
    sys.exit(app.exec())

