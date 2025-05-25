"""
Script de empacotamento para criar um executável Windows do Race Telemetry Analyzer.
Utiliza PyInstaller para criar um arquivo .exe standalone.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def create_executable(output_dir, icon_path=None, one_file=True, console=False):
    """
    Cria um executável Windows do Race Telemetry Analyzer.
    
    Args:
        output_dir: Diretório de saída para o executável
        icon_path: Caminho para o ícone do aplicativo (opcional)
        one_file: Se True, cria um único arquivo executável
        console: Se True, mostra a janela de console
    
    Returns:
        Caminho para o executável gerado
    """
    print("Iniciando processo de empacotamento...")
    
    # Verifica se o PyInstaller está instalado
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Verifica dependências
    print("Verificando dependências...")
    dependencies = [
        "PyQt6", "numpy", "matplotlib", "scipy", "pandas"
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            print(f"Instalando {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
    
    # Cria o diretório de saída se não existir
    os.makedirs(output_dir, exist_ok=True)
    
    # Caminho para o script principal
    main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "main.py")
    
    # Opções do PyInstaller
    pyinstaller_args = [
        main_script,
        "--name=RaceTelemetryAnalyzer",
        f"--distpath={output_dir}",
        "--clean",
        "--noconfirm"
    ]
    
    # Adiciona opções adicionais
    if one_file:
        pyinstaller_args.append("--onefile")
    else:
        pyinstaller_args.append("--onedir")
    
    if not console:
        pyinstaller_args.append("--noconsole")
    
    if icon_path:
        pyinstaller_args.append(f"--icon={icon_path}")
    
    # Adiciona dados adicionais
    data_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "ui"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    ]
    
    for data_dir in data_dirs:
        if os.path.exists(data_dir):
            pyinstaller_args.append(f"--add-data={data_dir}{os.pathsep}.")
    
    # Executa o PyInstaller
    print("Executando PyInstaller com os seguintes argumentos:")
    print(" ".join(pyinstaller_args))
    
    subprocess.check_call([sys.executable, "-m", "PyInstaller"] + pyinstaller_args)
    
    # Caminho para o executável gerado
    if one_file:
        exe_path = os.path.join(output_dir, "RaceTelemetryAnalyzer.exe")
    else:
        exe_path = os.path.join(output_dir, "RaceTelemetryAnalyzer", "RaceTelemetryAnalyzer.exe")
    
    print(f"Executável gerado com sucesso: {exe_path}")
    return exe_path


def create_installer(exe_path, output_dir, version="1.0.0"):
    """
    Cria um instalador Windows para o Race Telemetry Analyzer.
    
    Args:
        exe_path: Caminho para o executável gerado
        output_dir: Diretório de saída para o instalador
        version: Versão do aplicativo
    
    Returns:
        Caminho para o instalador gerado
    """
    print("Criando instalador Windows...")
    
    # Verifica se o NSIS está instalado
    nsis_path = shutil.which("makensis")
    if not nsis_path:
        print("AVISO: NSIS não encontrado. O instalador não será criado.")
        print("Para criar um instalador, instale o NSIS (Nullsoft Scriptable Install System).")
        return None
    
    # Cria o script NSIS
    nsis_script = os.path.join(output_dir, "installer.nsi")
    
    with open(nsis_script, "w") as f:
        f.write(f"""
; Instalador para Race Telemetry Analyzer
!include "MUI2.nsh"

; Informações do aplicativo
Name "Race Telemetry Analyzer"
OutFile "{output_dir}\\RaceTelemetryAnalyzer-{version}-setup.exe"
InstallDir "$PROGRAMFILES\\Race Telemetry Analyzer"
InstallDirRegKey HKCU "Software\\Race Telemetry Analyzer" ""

; Interface
!define MUI_ABORTWARNING
!define MUI_ICON "{exe_path}"

; Páginas
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Idiomas
!insertmacro MUI_LANGUAGE "Portuguese"

; Seção de instalação
Section "Instalar" SecInstall
  SetOutPath "$INSTDIR"
  
  ; Arquivos do aplicativo
  File "{exe_path}"
  
  ; Cria atalhos
  CreateDirectory "$SMPROGRAMS\\Race Telemetry Analyzer"
  CreateShortcut "$SMPROGRAMS\\Race Telemetry Analyzer\\Race Telemetry Analyzer.lnk" "$INSTDIR\\RaceTelemetryAnalyzer.exe"
  CreateShortcut "$DESKTOP\\Race Telemetry Analyzer.lnk" "$INSTDIR\\RaceTelemetryAnalyzer.exe"
  
  ; Registro de desinstalação
  WriteRegStr HKCU "Software\\Race Telemetry Analyzer" "" $INSTDIR
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Race Telemetry Analyzer" "DisplayName" "Race Telemetry Analyzer"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Race Telemetry Analyzer" "UninstallString" "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Race Telemetry Analyzer" "DisplayVersion" "{version}"
  WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Race Telemetry Analyzer" "Publisher" "Race Telemetry Analyzer"
SectionEnd

; Seção de desinstalação
Section "Uninstall"
  Delete "$INSTDIR\\RaceTelemetryAnalyzer.exe"
  Delete "$INSTDIR\\Uninstall.exe"
  
  Delete "$SMPROGRAMS\\Race Telemetry Analyzer\\Race Telemetry Analyzer.lnk"
  Delete "$DESKTOP\\Race Telemetry Analyzer.lnk"
  RMDir "$SMPROGRAMS\\Race Telemetry Analyzer"
  
  RMDir "$INSTDIR"
  
  DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Race Telemetry Analyzer"
  DeleteRegKey HKCU "Software\\Race Telemetry Analyzer"
SectionEnd
""")
    
    # Executa o NSIS
    subprocess.check_call([nsis_path, nsis_script])
    
    # Caminho para o instalador gerado
    installer_path = os.path.join(output_dir, f"RaceTelemetryAnalyzer-{version}-setup.exe")
    
    print(f"Instalador gerado com sucesso: {installer_path}")
    return installer_path


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Empacota o Race Telemetry Analyzer como um executável Windows.")
    parser.add_argument("--output-dir", default="dist", help="Diretório de saída para o executável")
    parser.add_argument("--icon", help="Caminho para o ícone do aplicativo")
    parser.add_argument("--onedir", action="store_true", help="Cria um diretório com arquivos separados em vez de um único executável")
    parser.add_argument("--console", action="store_true", help="Mostra a janela de console")
    parser.add_argument("--no-installer", action="store_true", help="Não cria um instalador")
    parser.add_argument("--version", default="1.0.0", help="Versão do aplicativo")
    
    args = parser.parse_args()
    
    # Cria o executável
    exe_path = create_executable(
        args.output_dir,
        args.icon,
        not args.onedir,
        args.console
    )
    
    # Cria o instalador
    if not args.no_installer:
        installer_path = create_installer(exe_path, args.output_dir, args.version)
        if installer_path:
            print(f"Processo concluído. Instalador disponível em: {installer_path}")
    else:
        print(f"Processo concluído. Executável disponível em: {exe_path}")


if __name__ == "__main__":
    main()
