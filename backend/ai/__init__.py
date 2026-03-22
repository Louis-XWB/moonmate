# Auto Trading Agent - AI Layer
# AI signal layer: sentiment analysis, hot topic detection, signal generation

from .signal_generator import AISignalGenerator
from .sentiment import SentimentAnalyzer

__all__ = ['AISignalGenerator', 'SentimentAnalyzer']
