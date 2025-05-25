"""
Widget de visualização de traçado da pista para o Race Telemetry Analyzer.
Exibe o traçado da pista e a posição atual do carro.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, pyqtSlot
from typing import List, Tuple, Dict, Any, Optional

import numpy as np


class TrackViewWidget(QWidget):
    """Widget para visualização do traçado da pista."""
    
    def __init__(self, parent=None):
        """
        Inicializa o widget de visualização da pista.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        # Configuração do widget
        self.setMinimumSize(300, 200)
        
        # Dados do traçado
        self.track_points = []
        self.lap_points = []
        self.current_position = None
        self.highlighted_point = None
        
        # Transformação de coordenadas
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # Cores
        self.track_color = QColor(100, 100, 100, 150)  # Cinza semi-transparente
        self.lap_color = QColor(0, 120, 255)  # Azul
        self.current_position_color = QColor(255, 0, 0)  # Vermelho
        self.highlight_color = QColor(255, 255, 0)  # Amarelo
        
        # Configuração visual
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(30, 30, 30))  # Fundo escuro
        self.setPalette(palette)
    
    def set_track_points(self, points: List[List[float]]):
        """
        Define os pontos do traçado da pista.
        
        Args:
            points: Lista de pontos [x, y]
        """
        self.track_points = points
        self._calculate_transformation()
        self.update()
    
    def set_lap_points(self, points: List[List[float]]):
        """
        Define os pontos do traçado da volta atual.
        
        Args:
            points: Lista de pontos [x, y]
        """
        self.lap_points = points
        self.update()
    
    def update_current_position(self, position: List[float]):
        """
        Atualiza a posição atual do carro.
        
        Args:
            position: Posição [x, y]
        """
        self.current_position = position
        self.update()
    
    def highlight_point(self, point: List[float]):
        """
        Destaca um ponto específico no traçado.
        
        Args:
            point: Posição [x, y]
        """
        self.highlighted_point = point
        self.update()
    
    def _calculate_transformation(self):
        """Calcula a transformação de coordenadas para exibir o traçado."""
        if not self.track_points:
            return
        
        # Encontra os limites do traçado
        x_values = [p[0] for p in self.track_points]
        y_values = [p[1] for p in self.track_points]
        
        min_x = min(x_values)
        max_x = max(x_values)
        min_y = min(y_values)
        max_y = max(y_values)
        
        # Calcula o fator de escala
        width = max_x - min_x
        height = max_y - min_y
        
        if width <= 0 or height <= 0:
            return
        
        # Adiciona margem
        margin = 0.1  # 10% de margem
        min_x -= width * margin
        max_x += width * margin
        min_y -= height * margin
        max_y += height * margin
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Calcula o fator de escala para ajustar ao tamanho do widget
        scale_x = self.width() / width if width > 0 else 1
        scale_y = self.height() / height if height > 0 else 1
        
        # Usa o menor fator para manter a proporção
        self.scale_factor = min(scale_x, scale_y)
        
        # Calcula o deslocamento para centralizar
        self.offset_x = (self.width() - width * self.scale_factor) / 2 - min_x * self.scale_factor
        self.offset_y = (self.height() - height * self.scale_factor) / 2 - min_y * self.scale_factor
    
    def _transform_point(self, point: List[float]) -> QPointF:
        """
        Transforma um ponto do espaço do mundo para o espaço do widget.
        
        Args:
            point: Ponto [x, y] no espaço do mundo
            
        Returns:
            Ponto transformado no espaço do widget
        """
        x = point[0] * self.scale_factor + self.offset_x
        y = point[1] * self.scale_factor + self.offset_y
        return QPointF(x, y)
    
    def paintEvent(self, event):
        """
        Manipula o evento de pintura do widget.
        
        Args:
            event: Evento de pintura
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Recalcula a transformação se o tamanho do widget mudou
        if self.track_points:
            self._calculate_transformation()
        
        # Desenha o traçado da pista
        if self.track_points:
            pen = QPen(self.track_color)
            pen.setWidth(3)
            painter.setPen(pen)
            
            path = QPainterPath()
            first_point = self._transform_point(self.track_points[0])
            path.moveTo(first_point)
            
            for point in self.track_points[1:]:
                path.lineTo(self._transform_point(point))
            
            painter.drawPath(path)
        
        # Desenha o traçado da volta atual
        if self.lap_points:
            pen = QPen(self.lap_color)
            pen.setWidth(2)
            painter.setPen(pen)
            
            path = QPainterPath()
            first_point = self._transform_point(self.lap_points[0])
            path.moveTo(first_point)
            
            for point in self.lap_points[1:]:
                path.lineTo(self._transform_point(point))
            
            painter.drawPath(path)
        
        # Desenha a posição atual
        if self.current_position:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self.current_position_color))
            
            pos = self._transform_point(self.current_position)
            painter.drawEllipse(pos, 5, 5)
        
        # Desenha o ponto destacado
        if self.highlighted_point:
            painter.setPen(QPen(self.highlight_color, 2))
            painter.setBrush(QBrush(self.highlight_color))
            
            pos = self._transform_point(self.highlighted_point)
            painter.drawEllipse(pos, 7, 7)
    
    def resizeEvent(self, event):
        """
        Manipula o evento de redimensionamento do widget.
        
        Args:
            event: Evento de redimensionamento
        """
        super().resizeEvent(event)
        self._calculate_transformation()
