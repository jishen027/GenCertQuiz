"""
Multi-Agent System for High-Quality Question Generation.

This module implements the three-agent architecture:
1. Researcher: Extracts core facts from textbook content
2. Psychometrician: Drafts questions matching exam style
3. Critic: Quality gate with reflection and iteration
"""

from .base_agent import BaseAgent
from .researcher import ResearcherAgent
from .psychometrician import PsychometricianAgent
from .critic import CriticAgent

__all__ = [
    'BaseAgent',
    'ResearcherAgent',
    'PsychometricianAgent',
    'CriticAgent'
]