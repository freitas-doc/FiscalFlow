# diagnostico_impressora.py
# Execute este arquivo para verificar por que as impressoras não aparecem.
# Rode com: python diagnostico_impressora.py

import sys
import subprocess

print("=" * 55)
print("  DIAGNÓSTICO DE IMPRESSORAS — DHL Organizador de NF")
print("=" * 55)

# ── 1. Sistema operacional ────────────────────────────────
print(f"\n[1] Sistema: {sys.platform} | Python {sys.version.split()[0]}")

# ── 2. Verifica pywin32 ───────────────────────────────────
print("\n[2] Verificando pywin32...")
try:
    import win32print
    print("    ✅ win32print importado com sucesso.")
except ImportError:
    print("    ❌ win32print NÃO encontrado.")
    print("    👉 Solução: abra o terminal e execute:")
    print("       pip install pywin32")
    print("       python -m pywin32_postinstall -install")
    sys.exit(1)

# ── 3. Lista todas as impressoras via win32print ──────────
print("\n[3] Impressoras via win32print.EnumPrinters()...")
try:
    flags = (
        win32print.PRINTER_ENUM_LOCAL |
        win32print.PRINTER_ENUM_CONNECTIONS
    )
    impressoras = win32print.EnumPrinters(flags)
    if impressoras:
        for p in impressoras:
            print(f"    ✅ Encontrada: [{p[2]}]")
    else:
        print("    ⚠️  Nenhuma impressora retornada por EnumPrinters.")
except Exception as e:
    print(f"    ❌ Erro ao chamar EnumPrinters: {e}")

# ── 4. Impressora padrão ──────────────────────────────────
print("\n[4] Impressora padrão do sistema...")
try:
    padrao = win32print.GetDefaultPrinter()
    print(f"    ✅ Padrão: [{padrao}]")
except Exception as e:
    print(f"    ❌ Erro ao obter impressora padrão: {e}")
    print("    ⚠️  Pode não haver impressora padrão definida no Windows.")

# ── 5. Lista via PowerShell (independente do pywin32) ─────
print("\n[5] Impressoras via PowerShell (verificação independente)...")
try:
    resultado = subprocess.run(
        ["powershell", "-Command",
         "Get-Printer | Select-Object Name, PrinterStatus | Format-Table -AutoSize"],
        capture_output=True, text=True, timeout=10
    )
    if resultado.stdout.strip():
        print(resultado.stdout)
    else:
        print("    ⚠️  PowerShell não retornou impressoras.")
    if resultado.stderr:
        print(f"    Stderr: {resultado.stderr[:200]}")
except FileNotFoundError:
    print("    ⚠️  PowerShell não encontrado.")
except Exception as e:
    print(f"    ❌ Erro no PowerShell: {e}")

# ── 6. Lista via wmic (fallback clássico) ─────────────────
print("\n[6] Impressoras via WMIC...")
try:
    resultado = subprocess.run(
        ["wmic", "printer", "get", "name,default,status"],
        capture_output=True, text=True, timeout=10
    )
    if resultado.stdout.strip():
        print(resultado.stdout)
    else:
        print("    ⚠️  WMIC não retornou impressoras.")
except FileNotFoundError:
    print("    ⚠️  WMIC não disponível nesta versão do Windows.")
except Exception as e:
    print(f"    ❌ Erro WMIC: {e}")

# ── 7. Versão do pywin32 ──────────────────────────────────
print("\n[7] Versão do pywin32...")
try:
    import win32api
    build = win32api.GetFileVersionInfo(
        win32api.__file__, "\\")
    ms = build['FileVersionMS']
    ls = build['FileVersionLS']
    print(f"    Versão: {ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}")
except Exception:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "pywin32"],
            capture_output=True, text=True)
        for linha in result.stdout.splitlines():
            if "Version" in linha:
                print(f"    {linha}")
    except Exception:
        print("    Não foi possível determinar a versão.")

print("\n" + "=" * 55)
print("  Diagnóstico concluído. Cole o resultado acima no chat.")
print("=" * 55)
input("\nPressione ENTER para fechar...")
