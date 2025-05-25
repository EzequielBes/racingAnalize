"""
Módulo principal do Race Telemetry Analyzer.
Inicializa a aplicação e a interface gráfica.
"""

import os
import sys
import logging
from datetime import datetime

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
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, QMessageBox
    from PyQt6.QtGui import QIcon, QFont, QPalette, QColor
    from PyQt6.QtCore import Qt, QSize
    
    # Imports dos widgets da UI
    from src.ui.dashboard_widget import DashboardWidget
    from src.ui.telemetry_widget import TelemetryChart # Usado como exemplo, pode ser um widget mais completo
    from src.ui.comparison_widget import ComparisonWidget
    from src.ui.setup_widget import SetupWidget
    
except ImportError as e:
    logger.critical(f"Erro fatal ao importar dependências PyQt ou UI: {str(e)}", exc_info=True)
    print(f"Erro fatal ao importar dependências PyQt ou UI: {str(e)}")
    print("Certifique-se de que PyQt6 e os módulos da UI estão instalados e acessíveis.")
    # Tenta mostrar uma mensagem de erro gráfica se QApplication puder ser instanciado
    try:
        app = QApplication([])
        QMessageBox.critical(None, "Erro Crítico", f"Não foi possível carregar componentes essenciais da interface: {e}. Verifique a instalação e os logs.")
    except Exception:
        pass # Se nem QApplication funcionar, só resta o console
    sys.exit(1)


class MainWindow(QMainWindow):
    """Janela principal do Race Telemetry Analyzer."""
    
    def __init__(self):
        super().__init__()
        logger.info("Inicializando MainWindow...")
        try:
            self.setWindowTitle("Race Telemetry Analyzer")
            self.setMinimumSize(1200, 800)
            self._setup_dark_theme()
            
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            layout = QVBoxLayout(central_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            
            self.tabs = QTabWidget()
            self.tabs.setTabPosition(QTabWidget.TabPosition.North)
            self.tabs.setMovable(True)
            layout.addWidget(self.tabs)
            
            self._setup_tabs()
            
            self.statusBar().showMessage("Pronto")
            self._center_window()
            logger.info("MainWindow inicializada com sucesso.")
            
        except Exception as e:
             logger.critical("Erro crítico durante a inicialização da MainWindow", exc_info=True)
             QMessageBox.critical(self, "Erro de Inicialização", f"Ocorreu um erro inesperado ao iniciar a janela principal: {e}. O aplicativo pode não funcionar corretamente.")
             # Considerar fechar a aplicação aqui dependendo da severidade
             # self.close()

    def _setup_dark_theme(self):
        # (Código do tema escuro - sem alterações, assume que é seguro)
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
        """)

    def _setup_tabs(self):
        """Configura as tabs da aplicação com tratamento de erro individual."""
        tab_configs = [
            {"name": "Dashboard", "widget_class": DashboardWidget},
            # {"name": "Análise de Telemetria", "widget_class": TelemetryAnalysisWidget}, # Substituir por widget real
            {"name": "Comparação de Voltas", "widget_class": ComparisonWidget},
            {"name": "Setups", "widget_class": SetupWidget},
            # {"name": "Configurações", "widget_class": SettingsWidget} # Adicionar widget de configurações
        ]

        for config in tab_configs:
            tab_name = config["name"]
            widget_class = config["widget_class"]
            try:
                widget_instance = widget_class()
                self.tabs.addTab(widget_instance, tab_name)
                logger.info(f"Tab 	'{tab_name}	' carregada com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao carregar a tab 	'{tab_name}	'", exc_info=True)
                # Adiciona uma tab vazia como placeholder e mostra erro
                placeholder_widget = QWidget()
                error_layout = QVBoxLayout(placeholder_widget)
                error_label = QLabel(f"Erro ao carregar o módulo '{tab_name}'.\nConsulte os logs para detalhes.")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_layout.addWidget(error_label)
                self.tabs.addTab(placeholder_widget, f"{tab_name} (Erro)")
                QMessageBox.warning(self, "Erro de Carregamento", f"Não foi possível carregar a aba '{tab_name}':\n{e}")
        
        # Adiciona tabs que não foram carregadas dinamicamente (ex: Telemetria, Configurações)
        # Se estas também precisarem de lógica complexa, mova para tab_configs
        try:
             telemetry_tab = QWidget()
             telemetry_layout = QVBoxLayout(telemetry_tab)
             # TODO: Substituir TelemetryChart por um widget de análise mais completo se necessário
             telemetry_chart = TelemetryChart() 
             telemetry_layout.addWidget(telemetry_chart)
             self.tabs.addTab(telemetry_tab, "Análise de Telemetria")
             logger.info("Tab 'Análise de Telemetria' carregada com sucesso.")
        except Exception as e:
             logger.error("Erro ao carregar a tab 'Análise de Telemetria'", exc_info=True)
             self.tabs.addTab(QWidget(), "Análise de Telemetria (Erro)")
             QMessageBox.warning(self, "Erro de Carregamento", f"Não foi possível carregar a aba 'Análise de Telemetria':\n{e}")

        try:
             settings_tab = QWidget() # Placeholder para configurações
             # TODO: Implementar widget de configurações
             self.tabs.addTab(settings_tab, "Configurações")
             logger.info("Tab 'Configurações' carregada com sucesso (placeholder).")
        except Exception as e:
             logger.error("Erro ao carregar a tab 'Configurações'", exc_info=True)
             self.tabs.addTab(QWidget(), "Configurações (Erro)")
             QMessageBox.warning(self, "Erro de Carregamento", f"Não foi possível carregar a aba 'Configurações':\n{e}")

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
        # Exemplo: 
        # dashboard = self.tabs.findChild(DashboardWidget)
        # if dashboard and dashboard.capture_manager.is_capturing:
        #     dashboard.capture_manager.stop_capture()
        #     dashboard.capture_manager.disconnect()
        super().closeEvent(event)


def main():
    """Função principal com tratamento de exceção global."""
    # Configura um hook para exceções não tratadas
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Permite Ctrl+C funcionar normalmente no console
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.critical("Exceção não tratada capturada!", exc_info=(exc_type, exc_value, exc_traceback))
        # Tenta mostrar uma mensagem de erro gráfica
        try:
             app_instance = QApplication.instance()
             if app_instance:
                  error_message = f"Ocorreu um erro inesperado:\n\n{exc_value}\n\nConsulte o arquivo de log para detalhes:\n{log_file}"
                  QMessageBox.critical(None, "Erro Inesperado", error_message)
        except Exception as msg_err:
             logger.error(f"Erro ao exibir a caixa de diálogo de erro: {msg_err}")
        finally:
             # Garante que a aplicação feche após um erro crítico não tratado
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
        # Este bloco captura erros que podem ocorrer *antes* do loop de eventos iniciar
        # ou se o sys.excepthook falhar.
        logger.critical(f"Erro crítico irrecuperável na inicialização da aplicação: {str(e)}", exc_info=True)
        print(f"Erro crítico irrecuperável na inicialização da aplicação: {str(e)}")
        # Tenta mostrar mensagem gráfica uma última vez
        try:
             app = QApplication([])
             QMessageBox.critical(None, "Erro Crítico", f"Erro irrecuperável na inicialização: {e}. Verifique os logs.")
        except Exception:
             pass
        sys.exit(1)

if __name__ == "__main__":
    main()

