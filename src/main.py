# -*- coding: utf-8 -*-
"""
Módulo principal do Race Telemetry Analyzer.
Inicializa a aplicação e a interface gráfica, integrando o fluxo de importação e análise.
"""

import os
import sys
import logging
from datetime import datetime
import numpy as np # Necessário para o código de exemplo do AnalysisWidget

# --- Configuração de Logging --- 
log_dir = os.path.join(os.path.expanduser("~"), "RaceTelemetryAnalyzer", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"rta_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler() # Mantém o log no console também
    ]
)
logger = logging.getLogger("race_telemetry_main")

# Adiciona o diretório pai ao path para permitir imports absolutos
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                                 QWidget, QMessageBox, QLabel, QFileDialog, QMenuBar, 
                                 QStatusBar)
    from PyQt6.QtGui import QIcon, QFont, QPalette, QColor, QAction
    from PyQt6.QtCore import Qt, QSize

    # Imports dos componentes principais
    from src.telemetry_import import TelemetryImporter
    from src.processing_analysis.telemetry_processor import TelemetryProcessor
    from src.core.standard_data import TelemetrySession, SessionInfo, LapData, DataPoint, TrackData # Adicionado para exemplo

    # Imports dos widgets da UI
    from src.ui.dashboard_widget import DashboardWidget # Placeholder
    from src.ui.telemetry_widget import TelemetryChart # Placeholder
    from src.ui.comparison_widget import ComparisonWidget
    from src.ui.analysis_widget import AnalysisWidget # <<< ADICIONADO
    from src.ui.setup_widget import SetupWidget # Placeholder

except ImportError as e:
    logger.critical(f"Erro fatal ao importar dependências PyQt ou módulos do projeto: {str(e)}", exc_info=True)
    print(f"Erro fatal ao importar dependências PyQt ou módulos do projeto: {str(e)}")
    print("Certifique-se de que PyQt6, pyqtgraph e os módulos da UI estão instalados e acessíveis.")
    try:
        app = QApplication([])
        QMessageBox.critical(None, "Erro Crítico", f"Não foi possível carregar componentes essenciais: {e}. Verifique a instalação e os logs.")
    except Exception:
        pass
    sys.exit(1)


class MainWindow(QMainWindow):
    """Janela principal do Race Telemetry Analyzer."""

    def __init__(self):
        super().__init__()
        logger.info("Inicializando MainWindow...")
        self.current_session: Optional[TelemetrySession] = None
        self.importer = TelemetryImporter()
        self.tab_widgets = {} # Inicializa aqui para garantir que existe

        try:
            self.setWindowTitle("Race Telemetry Analyzer")
            self.setMinimumSize(1200, 800)
            self._setup_dark_theme()

            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            layout.setContentsMargins(0, 0, 0, 0)

            self._setup_menu_bar()

            self.tabs = QTabWidget()
            self.tabs.setTabPosition(QTabWidget.TabPosition.North)
            self.tabs.setMovable(True)
            layout.addWidget(self.tabs)

            self._setup_tabs()

            self.setStatusBar(QStatusBar())
            self.statusBar().showMessage("Pronto. Use Arquivo > Importar para carregar dados.")
            self._center_window()
            logger.info("MainWindow inicializada com sucesso.")

        except Exception as e:
             logger.critical("Erro crítico durante a inicialização da MainWindow", exc_info=True)
             QMessageBox.critical(self, "Erro de Inicialização", f"Ocorreu um erro inesperado ao iniciar a janela principal: {e}. O aplicativo pode não funcionar corretamente.")

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Arquivo")

        import_action = QAction("&Importar Arquivo de Telemetria...", self)
        import_action.triggered.connect(self.import_telemetry_file)
        file_menu.addAction(import_action)

        # Adicionar ação de Sair
        exit_action = QAction("&Sair", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _setup_dark_theme(self):
        # (Código do tema escuro - sem alterações)
        palette = QPalette()
        background_color = QColor(30, 30, 30)
        text_color = QColor(240, 240, 240)
        highlight_color = QColor(42, 130, 218)
        palette.setColor(QPalette.ColorRole.Window, background_color)
        palette.setColor(QPalette.ColorRole.WindowText, text_color)
        palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 35))
        palette.setColor(QPalette.ColorRole.ToolTipBase, background_color)
        palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Button, background_color)
        palette.setColor(QPalette.ColorRole.ButtonText, text_color)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, highlight_color)
        palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)
        self.setStyleSheet("""
            QMenuBar { background-color: #2A2A2A; color: #DADADA; }
            QMenuBar::item:selected { background-color: #3A3A3A; }
            QMenu { background-color: #2A2A2A; color: #DADADA; border: 1px solid #505050; }
            QMenu::item:selected { background-color: #3A3A3A; }
            QTabWidget::pane { border: 1px solid #3A3A3A; background-color: #2A2A2A; }
            QTabBar::tab { background-color: #2A2A2A; color: #DADADA; padding: 8px 16px; border: 1px solid #3A3A3A; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: #3A3A3A; border-bottom: none; }
            QTabBar::tab:hover { background-color: #3A3A3A; }
            QPushButton { background-color: #3A3A3A; color: #DADADA; border: 1px solid #505050; padding: 5px 10px; border-radius: 3px; }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #2A80DA; }
            QComboBox { background-color: #3A3A3A; color: #DADADA; border: 1px solid #505050; padding: 5px; border-radius: 3px; }
            QLineEdit { background-color: #3A3A3A; color: #DADADA; border: 1px solid #505050; padding: 5px; border-radius: 3px; }
            QLabel#section-title { font-size: 16px; font-weight: bold; color: #DADADA; }
            QLabel#metric-value { font-size: 14px; font-weight: bold; color: #2A80DA; }
            QStatusBar { color: #DADADA; }
        """)

    def _setup_tabs(self):
        """Configura as tabs da aplicação com tratamento de erro individual."""
        # Guarda referências aos widgets das tabs para poder atualizá-los
        self.tab_widgets = {}

        tab_configs = [
            # {"name": "Dashboard", "widget_class": DashboardWidget, "id": "dashboard"}, # Requer implementação real
            {"name": "Análise Detalhada", "widget_class": AnalysisWidget, "id": "analysis"}, # <<< ADICIONADO
            {"name": "Comparação de Voltas", "widget_class": ComparisonWidget, "id": "comparison"},
            # {"name": "Setups", "widget_class": SetupWidget, "id": "setups"}, # Requer implementação real
            # {"name": "Configurações", "widget_class": SettingsWidget, "id": "settings"} # Adicionar widget de configurações
        ]

        for config in tab_configs:
            tab_name = config["name"]
            widget_class = config["widget_class"]
            tab_id = config["id"]
            try:
                # Cria a instância do widget
                widget_instance = widget_class()
                self.tabs.addTab(widget_instance, tab_name)
                self.tab_widgets[tab_id] = widget_instance # Armazena a referência
                logger.info(f"Tab 	'{tab_name}	' carregada com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao carregar a tab 	'{tab_name}	'", exc_info=True)
                placeholder_widget = QWidget()
                error_layout = QVBoxLayout(placeholder_widget)
                error_label = QLabel(f"Erro ao carregar o módulo '{tab_name}'.\nConsulte os logs para detalhes.")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_layout.addWidget(error_label)
                self.tabs.addTab(placeholder_widget, f"{tab_name} (Erro)")
                QMessageBox.warning(self, "Erro de Carregamento", f"Não foi possível carregar a aba '{tab_name}':\n{e}")

    def import_telemetry_file(self):
        """Abre um diálogo para selecionar e importar um arquivo de telemetria."""
        file_filter = "Arquivos de Telemetria (*.ld *.ldx *.ibt);;Todos os Arquivos (*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Importar Arquivo de Telemetria", "", file_filter)

        if not file_path:
            logger.info("Importação cancelada pelo usuário.")
            return

        self.statusBar().showMessage(f"Importando {os.path.basename(file_path)}...")
        QApplication.processEvents() # Atualiza a UI

        try:
            # Importa e normaliza
            normalized_session = self.importer.import_and_normalize(file_path)

            if not normalized_session:
                QMessageBox.critical(self, "Erro de Importação", f"Não foi possível importar ou normalizar o arquivo: {os.path.basename(file_path)}.\nVerifique os logs para detalhes.")
                self.statusBar().showMessage("Falha na importação.")
                return

            self.current_session = normalized_session
            logger.info(f"Sessão carregada: {self.current_session.session_info.game} - {self.current_session.session_info.track}")
            self.statusBar().showMessage(f"Processando {os.path.basename(file_path)}...")
            QApplication.processEvents()

            # Processa a sessão normalizada (pode incluir cálculos adicionais)
            # Por enquanto, o processamento principal está dentro dos widgets
            # processor = TelemetryProcessor(self.current_session)
            # processor.process_all_laps()
            # processed_data = processor.processed_data
            processed_data = self.current_session # Passa a sessão normalizada diretamente

            # Carrega os dados processados nos widgets relevantes
            self._load_data_into_widgets(processed_data)

            # TODO: Carregar dados em outras tabs (Dashboard se ativo, etc.)

        except FileNotFoundError as fnf_err:
            logger.error(f"Erro: Arquivo não encontrado durante importação: {fnf_err}")
            QMessageBox.critical(self, "Erro de Arquivo", f"Arquivo não encontrado:\n{fnf_err}")
            self.statusBar().showMessage("Erro na importação: Arquivo não encontrado.")
        except ValueError as val_err:
            logger.error(f"Erro de valor/formato durante importação: {val_err}")
            QMessageBox.critical(self, "Erro de Formato", f"Erro ao processar o arquivo (formato inválido ou não suportado):\n{val_err}")
            self.statusBar().showMessage("Erro na importação: Formato inválido.")
        except NotImplementedError as ni_err:
            logger.error(f"Erro: Funcionalidade não implementada: {ni_err}")
            QMessageBox.warning(self, "Funcionalidade Pendente", f"O parser ou normalizador para este tipo de arquivo ainda não foi totalmente implementado:\n{ni_err}")
            self.statusBar().showMessage("Erro na importação: Funcionalidade pendente.")
        except Exception as e:
            logger.exception(f"Erro inesperado durante importação/processamento de {file_path}: {e}")
            QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro inesperado:\n{e}\nConsulte os logs para detalhes.")
            self.statusBar().showMessage("Erro inesperado durante importação.")

    def _load_data_into_widgets(self, session_data: TelemetrySession):
        """Carrega os dados da sessão nos widgets das tabs relevantes."""
        logger.info("Carregando dados da sessão nos widgets...")
        widgets_loaded = 0

        # Carrega na Análise Detalhada
        analysis_widget = self.tab_widgets.get("analysis")
        if analysis_widget and isinstance(analysis_widget, AnalysisWidget):
            try:
                analysis_widget.load_session_data(session_data)
                logger.info("Dados carregados na aba 'Análise Detalhada'.")
                widgets_loaded += 1
            except Exception as e:
                logger.error("Erro ao carregar dados na aba 'Análise Detalhada'", exc_info=True)
                QMessageBox.warning(self, "Erro Interno", f"Não foi possível carregar dados na aba 'Análise Detalhada':\n{e}")
        else:
            logger.warning("Widget 'Análise Detalhada' não encontrado ou tipo incorreto.")

        # Carrega na Comparação de Voltas
        comparison_widget = self.tab_widgets.get("comparison")
        if comparison_widget and isinstance(comparison_widget, ComparisonWidget):
            try:
                # O ComparisonWidget espera dados processados e info da sessão
                # Reutilizamos a sessão normalizada como 'processed_data' por enquanto
                comparison_widget.load_processed_session(session_data, session_data.session_info)
                logger.info("Dados carregados na aba 'Comparação de Voltas'.")
                widgets_loaded += 1
            except Exception as e:
                logger.error("Erro ao carregar dados na aba 'Comparação de Voltas'", exc_info=True)
                QMessageBox.warning(self, "Erro Interno", f"Não foi possível carregar dados na aba 'Comparação de Voltas':\n{e}")
        else:
            logger.warning("Widget 'Comparação de Voltas' não encontrado ou tipo incorreto.")

        # Atualiza status e foca em uma das tabs
        if widgets_loaded > 0:
            self.statusBar().showMessage(f"Sessão '{session_data.session_info.track}' carregada. Pronta para análise.")
            # Foca na primeira tab que conseguiu carregar (Análise ou Comparação)
            if analysis_widget and isinstance(analysis_widget, AnalysisWidget):
                 self.tabs.setCurrentWidget(analysis_widget)
            elif comparison_widget and isinstance(comparison_widget, ComparisonWidget):
                 self.tabs.setCurrentWidget(comparison_widget)
        else:
             self.statusBar().showMessage("Sessão carregada, mas erro ao exibir nas abas de análise.")

    def _center_window(self):
        # (Código para centralizar - sem alterações)
        try:
            frame_geometry = self.frameGeometry()
            screen = QApplication.primaryScreen()
            if screen:
                 center_point = screen.availableGeometry().center()
                 frame_geometry.moveCenter(center_point)
                 self.move(frame_geometry.topLeft())
            else:
                 logger.warning("Não foi possível obter a tela primária para centralizar a janela.")
        except Exception as e:
             logger.error("Erro ao tentar centralizar a janela", exc_info=True)

    def closeEvent(self, event):
        """Sobrescreve o evento de fechamento para garantir limpeza."""
        logger.info("Fechando a aplicação...")
        # TODO: Adicionar lógica de limpeza se necessário (ex: parar threads de captura)
        super().closeEvent(event)


def main():
    """Função principal com tratamento de exceção global."""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Exceção não tratada capturada!", exc_info=(exc_type, exc_value, exc_traceback))
        try:
             app_instance = QApplication.instance()
             if app_instance:
                  error_message = f"Ocorreu um erro inesperado:\n\n{exc_value}\n\nConsulte o arquivo de log para detalhes:\n{log_file}"
                  QMessageBox.critical(None, "Erro Inesperado", error_message)
        except Exception as msg_err:
             logger.error(f"Erro ao exibir a caixa de diálogo de erro: {msg_err}")
        finally:
             sys.exit(1)

    sys.excepthook = handle_exception

    try:
        logger.info("Iniciando Race Telemetry Analyzer...")
        app = QApplication(sys.argv)
        app.setApplicationName("Race Telemetry Analyzer")

        window = MainWindow()
        window.show()

        logger.info("Aplicação iniciada, entrando no loop de eventos.")
        exit_code = app.exec()
        logger.info(f"Loop de eventos finalizado com código: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"Erro crítico irrecuperável na inicialização da aplicação: {str(e)}", exc_info=True)
        print(f"Erro crítico irrecuperável na inicialização da aplicação: {str(e)}")
        try:
             app = QApplication([])
             QMessageBox.critical(None, "Erro Crítico", f"Erro irrecuperável na inicialização: {e}. Verifique os logs.")
        except Exception:
             pass
        sys.exit(1)

if __name__ == "__main__":
    main()

