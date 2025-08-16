"""
Módulo para adicionar cores e formatação ao terminal.
Utiliza códigos ANSI para colorir a saída do terminal.
"""

class Colors:
    """Códigos de cores ANSI para o terminal."""
    
    # Cores básicas
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Cores brilhantes
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Estilos
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    STRIKETHROUGH = '\033[9m'
    
    # Reset
    RESET = '\033[0m'
    
    # Cores de fundo
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

def colorize(text, color_code):
    """
    Adiciona cor a um texto.
    
    Args:
        text (str): Texto a ser colorido.
        color_code (str): Código de cor ANSI.
        
    Returns:
        str: Texto colorido.
    """
    return f"{color_code}{text}{Colors.RESET}"

def success(text):
    """Retorna texto em verde (sucesso)."""
    return colorize(text, Colors.BRIGHT_GREEN)

def error(text):
    """Retorna texto em vermelho (erro)."""
    return colorize(text, Colors.BRIGHT_RED)

def warning(text):
    """Retorna texto em amarelo (aviso)."""
    return colorize(text, Colors.BRIGHT_YELLOW)

def info(text):
    """Retorna texto em azul (informação)."""
    return colorize(text, Colors.BRIGHT_BLUE)

def bold(text):
    """Retorna texto em negrito."""
    return colorize(text, Colors.BOLD)

def cyan(text):
    """Retorna texto em ciano."""
    return colorize(text, Colors.BRIGHT_CYAN)

def magenta(text):
    """Retorna texto em magenta."""
    return colorize(text, Colors.BRIGHT_MAGENTA)

def dim(text):
    """Retorna texto esmaecido."""
    return colorize(text, Colors.DIM)

def highlight(text):
    """Retorna texto destacado (negrito + ciano)."""
    return colorize(text, Colors.BOLD + Colors.BRIGHT_CYAN)

def header(text):
    """Retorna texto como cabeçalho (negrito + magenta)."""
    return colorize(text, Colors.BOLD + Colors.BRIGHT_MAGENTA)

def progress(text):
    """Retorna texto de progresso (ciano)."""
    return colorize(text, Colors.CYAN)

def commit_info(text):
    """Retorna texto de informação de commit (amarelo esmaecido)."""
    return colorize(text, Colors.YELLOW)
