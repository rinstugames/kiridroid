import os
import shutil
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import zipfile
import sys
import threading
import queue
import logging
import re
from PIL import Image

def play_sound(filename):
    try:
        import winsound
        winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass

APKTOOL_JAR = os.path.abspath("apktool_2.11.1.jar")
KIRIKIRI_APK = os.path.abspath("Kirikiroid2_1.3.9.apk")
BUILD_TOOLS = os.path.abspath("build-tools")
JAVA_BIN = os.path.abspath(os.path.join("openjdk-21.0.7.6-hotspot", "bin", "java.exe"))
if not os.path.exists(JAVA_BIN):
    raise RuntimeError(f"Java incorporado no encontrado: {JAVA_BIN}")

def find_apksigner():
    apksigner_bat = os.path.join(BUILD_TOOLS, "35.0.1", "apksigner.bat")
    apksigner_jar = os.path.join(BUILD_TOOLS, "35.0.1", "lib", "apksigner.jar")
    if os.path.exists(apksigner_bat):
        return apksigner_bat
    elif os.path.exists(apksigner_jar):
        return apksigner_jar
    apksigner_bat = os.path.join(BUILD_TOOLS, "36.0.0", "apksigner.bat")
    apksigner_jar = os.path.join(BUILD_TOOLS, "36.0.0", "lib", "apksigner.jar")
    if os.path.exists(apksigner_bat):
        return apksigner_bat
    elif os.path.exists(apksigner_jar):
        return apksigner_jar
    apksigner_bat = os.path.join(BUILD_TOOLS, "apksigner.bat")
    apksigner_jar = os.path.join(BUILD_TOOLS, "apksigner.jar")
    if os.path.exists(apksigner_bat):
        return apksigner_bat
    elif os.path.exists(apksigner_jar):
        return apksigner_jar
    return None

APKSIGNER = find_apksigner()
OUTPUT_DIR = os.path.abspath("output")
KEYSTORE = os.path.abspath("testkey.jks")
KEY_ALIAS = "testkey"
KEY_PASS = "123456"

def ensure_keystore(progress, status):
    if not os.path.exists(KEYSTORE):
        status.set("Creando keystore...")
        progress.step(10)
        progress.update()
        cmd = [
            "keytool", "-genkeypair", "-v",
            "-keystore", KEYSTORE,
            "-alias", KEY_ALIAS,
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-storepass", KEY_PASS,
            "-keypass", KEY_PASS,
            "-dname", "CN=Test,OU=Test,O=Test,L=Test,ST=Test,C=CN"
        ]
        subprocess.run(cmd, check=True)

def patch_manifest(manifest_path, package_name, app_name):
    with open(manifest_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    activity_replaced = False
    in_application = False
    for line in lines:
        if "package=" in line:
            line = line.replace(
                line.split('package="')[1].split('"')[0], package_name)
        if "android:label=" in line:
            line = line.replace(
                line.split('android:label="')[1].split('"')[0], app_name)
        if (not activity_replaced) and 'android:name=' in line and '<activity' in line:
            line = re.sub(r'android:name="[^"]+"', 'android:name="org.tvp.kirikiri2.KR2Activity"', line)
            activity_replaced = True
        if '<application' in line:
            in_application = True
            if 'android:extractNativeLibs' in line:
                line = re.sub(r'android:extractNativeLibs="[^"]*"', 'android:extractNativeLibs="true"', line)
            else:
                line = line.rstrip().replace('>', ' android:extractNativeLibs="true">')
        new_lines.append(line)
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def replace_icon(res_dir, icon_path):
    mipmap_dir = os.path.join(res_dir, "mipmap-xxxhdpi")
    if not os.path.exists(mipmap_dir):
        os.makedirs(mipmap_dir)
    shutil.copy(icon_path, os.path.join(mipmap_dir, "ic_launcher.png"))

def copy_game_assets(game_dir, assets_dir):
    if os.path.exists(assets_dir):
        shutil.rmtree(assets_dir)
    shutil.copytree(game_dir, assets_dir)
    data_xp3 = os.path.join(assets_dir, "data.xp3")
    gameexe_dat = os.path.join(assets_dir, "gameexe.dat")
    if os.path.exists(data_xp3) and not os.path.exists(gameexe_dat):
        shutil.copyfile(data_xp3, gameexe_dat)

logging.basicConfig(filename='log.txt', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class UIUpdater:
    def __init__(self, root, progress, status, btn):
        self.root = root
        self.progress = progress
        self.status = status
        self.btn = btn
    def set_status(self, text):
        self.root.after(0, self.status.set, text)
    def set_progress(self, value):
        def setter():
            self.progress['value'] = value
        self.root.after(0, setter)
    def step_progress(self, value):
        def stepper():
            self.progress.step(value)
        self.root.after(0, stepper)
    def show_info(self, title, msg):
        self.root.after(0, messagebox.showinfo, title, msg)
    def show_error(self, title, msg):
        play_sound("error.wav")
        self.root.after(0, messagebox.showerror, title, msg)
    def disable_btn(self):
        self.root.after(0, self.btn.config, {'state': 'disabled'})
    def enable_btn(self):
        self.root.after(0, self.btn.config, {'state': 'normal'})

def check_apktool_version():
    try:
        cmd = [JAVA_BIN, "-jar", APKTOOL_JAR, "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return "Desconocido"
    except Exception as e:
        return f"Error al verificar: {e}"

MIPMAP_INFO = {
    "mipmap-mdpi": (48, 48),
    "mipmap-hdpi": (72, 72),
    "mipmap-xhdpi": (96, 96),
    "mipmap-xxhdpi": (144, 144),
    "mipmap-xxxhdpi": (192, 192),
}

def replace_launcher_icons(res_dir, user_icon_path):
    from PIL import Image
    user_icon = Image.open(user_icon_path).convert("RGBA")
    replaced = 0
    drawable_dirs = [
        "drawable-hdpi-v4",
        "drawable-mdpi-v4",
        "drawable-xhdpi-v4",
        "drawable-xxhdpi-v4"
    ]
    for subdir in drawable_dirs:
        target_path = os.path.join(res_dir, subdir, "ic_launcher.png")
        if os.path.exists(target_path):
            with Image.open(target_path) as orig_icon:
                size = orig_icon.size
            resized_icon = user_icon.resize(size, Image.LANCZOS)
            resized_icon.save(target_path, format='PNG')
            replaced += 1
    if replaced == 0:
        raise RuntimeError("¡No se encontró ninguna carpeta drawable-*-v4, fallo al reemplazar el icono!")
    return replaced

def build_apk_thread(game_dir, icon_path, package_name, app_name, ui_updater, progress_max=100):
    original_java_home = os.environ.get('JAVA_HOME')
    original_path = os.environ.get('PATH')
    openjdk_dir = os.path.abspath('openjdk-21.0.7.6-hotspot')
    os.environ['JAVA_HOME'] = openjdk_dir
    os.environ['PATH'] = os.path.join(openjdk_dir, 'bin') + os.pathsep + (original_path or '')
    tmpdirs = []
    try:
        ui_updater.set_status("Creando keystore...")
        ui_updater.set_progress(0)
        ensure_keystore(ui_updater, ui_updater)
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdirs.append(tmpdir)
            ui_updater.set_status("Descompilando APK...")
            ui_updater.step_progress(10)
            decompiled_dir = os.path.join(tmpdir, "kirikiroid2")
            cmd = [JAVA_BIN, "-Xmx4g", "-jar", APKTOOL_JAR, "d", "-f", KIRIKIRI_APK, "-o", decompiled_dir]
            logging.info(f"Comando de descompilación: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True)
            logging.info(f"Resultado de descompilación: {result.stdout}\nError: {result.stderr}")
            if result.returncode != 0:
                play_sound("error.wav")
                ui_updater.show_error("Error", "¡Error al descompilar con apktool!\n" + result.stderr.decode("utf-8", errors="ignore"))
                ui_updater.set_status("Fallo en la descompilación")
                ui_updater.enable_btn()
                return
            ui_updater.set_status("Copiando recursos del juego...")
            ui_updater.step_progress(15)
            assets_dir = os.path.join(decompiled_dir, "assets")
            copy_game_assets(game_dir, assets_dir)
            ui_updater.set_status("Reemplazando iconos...")
            ui_updater.step_progress(10)
            res_dir = os.path.join(decompiled_dir, "res")
            try:
                replaced = replace_launcher_icons(res_dir, icon_path)
                logging.info(f"{replaced} ic_launcher.png reemplazado")
            except Exception as e:
                play_sound("error.wav")
                ui_updater.show_error("Error", f"Error al reemplazar el icono: {e}")
                ui_updater.set_status("Error al reemplazar el icono")
                ui_updater.enable_btn()
                return
            ui_updater.set_status("Cambiando nombre de paquete y app...")
            ui_updater.step_progress(10)
            manifest_path = os.path.join(decompiled_dir, "AndroidManifest.xml")
            patch_manifest(manifest_path, package_name, app_name)
            ui_updater.set_status("Reconstruyendo APK...")
            ui_updater.step_progress(20)
            rebuilt_apk = os.path.join(tmpdir, "rebuilt.apk")
            cmd = [JAVA_BIN, "-Xmx4g", "-jar", APKTOOL_JAR, "b", decompiled_dir, "-o", rebuilt_apk]
            logging.info(f"Comando de reconstrucción: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True)
            logging.info(f"Resultado de reconstrucción: {result.stdout}\nError: {result.stderr}")
            if result.returncode != 0:
                play_sound("error.wav")
                ui_updater.show_error("Error", "¡Error al reconstruir con apktool!\n" + result.stderr.decode("utf-8", errors="ignore"))
                ui_updater.set_status("Fallo en la reconstrucción")
                ui_updater.enable_btn()
                return
            try:
                SEVEN_ZIP = os.path.abspath(os.path.join(os.path.dirname(__file__), "7-Zip", "7z.exe"))
                with tempfile.TemporaryDirectory() as tmpdir_a, tempfile.TemporaryDirectory() as tmpdir_b:
                    with zipfile.ZipFile(rebuilt_apk, 'r') as zin:
                        zin.extractall(tmpdir_a)
                    with zipfile.ZipFile(KIRIKIRI_APK, 'r') as zin:
                        zin.extractall(tmpdir_b)
                    for fname in os.listdir(tmpdir_b):
                        if fname.startswith('classes') and fname.endswith('.dex'):
                            shutil.copy(os.path.join(tmpdir_b, fname), os.path.join(tmpdir_a, fname))
                    tmp_new_apk = rebuilt_apk + ".tmp"
                    result = subprocess.run([SEVEN_ZIP, 'a', '-tzip', tmp_new_apk, '.'], cwd=tmpdir_a, capture_output=True)
                    if result.returncode != 0:
                        raise Exception(f"Error de reconstrucción 7z: {result.stderr.decode('utf-8', errors='ignore')}")
                    os.replace(tmp_new_apk, rebuilt_apk)
                logging.info("DEX reemplazado correctamente vía 7z")
            except Exception as e:
                logging.error(f"Error al copiar DEX: {e}")
                ui_updater.show_error("Error", f"Error al copiar DEX: {e}")
                ui_updater.set_status("Error al copiar DEX")
                ui_updater.enable_btn()
                return
            try:
                with tempfile.TemporaryDirectory() as tmpdir_c:
                    with zipfile.ZipFile(rebuilt_apk, 'r') as zin:
                        zin.extractall(tmpdir_c)
                    lib_dir = os.path.join(tmpdir_c, "lib")
                    abi_map = {
                        "armeabi-v7a": os.path.abspath("libc++_shared/32/libc++_shared.so"),
                        "arm64-v8a": os.path.abspath("libc++_shared/64/libc++_shared.so")
                    }
                    for abi, so_src in abi_map.items():
                        abi_path = os.path.join(lib_dir, abi)
                        if not os.path.exists(so_src):
                            play_sound("error.wav")
                            ui_updater.show_error("Error", f"{so_src} no encontrado, verifique la presencia de libc++_shared.so 32/64 bits")
                            ui_updater.set_status(f"libc++_shared.so ausente para {abi}")
                            ui_updater.enable_btn()
                            return
                        if not os.path.exists(abi_path):
                            os.makedirs(abi_path)
                        shutil.copy(so_src, os.path.join(abi_path, "libc++_shared.so"))
                    for abi in abi_map.keys():
                        so_path = os.path.join(lib_dir, abi, "libc++_shared.so")
                        if not os.path.exists(so_path):
                            play_sound("error.wav")
                            ui_updater.show_error("Error", f"libc++_shared.so ausente en la carpeta ABI {abi}, ¡empaquetado cancelado!")
                            ui_updater.set_status("libc++_shared.so ausente en ABI")
                            ui_updater.enable_btn()
                            return
                    tmp_new_apk2 = rebuilt_apk + ".tmp2"
                    result = subprocess.run([SEVEN_ZIP, 'a', '-tzip', tmp_new_apk2, '.'], cwd=tmpdir_c, capture_output=True)
                    if result.returncode != 0:
                        raise Exception(f"Error de reconstrucción 7z: {result.stderr.decode('utf-8', errors='ignore')}")
                    os.replace(tmp_new_apk2, rebuilt_apk)
            except Exception as e:
                logging.error(f"Error al procesar libc++_shared.so: {e}")
                ui_updater.show_error("Error", f"Error al procesar libc++_shared.so: {e}")
                ui_updater.set_status("Error al procesar libc++_shared.so")
                ui_updater.enable_btn()
                return
            ui_updater.set_status("Firmando APK...")
            ui_updater.step_progress(20)
            signed_apk = os.path.join(OUTPUT_DIR, f"{app_name}_signed.apk")
            if not os.path.exists(rebuilt_apk):
                play_sound("error.wav")
                ui_updater.show_error("Error", f"APK reconstruido no encontrado: {rebuilt_apk}")
                ui_updater.set_status("APK reconstruido no encontrado")
                ui_updater.enable_btn()
                return
            rebuilt_size = os.path.getsize(rebuilt_apk)
            if rebuilt_size < 1000000:
                play_sound("error.wav")
                ui_updater.show_error("Error", f"APK reconstruido puede estar dañado, tamaño: {rebuilt_size} bytes")
                ui_updater.set_status("APK reconstruido dañado")
                ui_updater.enable_btn()
                return
            if APKSIGNER is None:
                play_sound("error.wav")
                ui_updater.show_error("Error", "¡Herramienta apksigner no encontrada! Verifique la carpeta build-tools.")
                ui_updater.set_status("apksigner no encontrado")
                ui_updater.enable_btn()
                return
            if APKSIGNER.endswith(".bat"):
                bat_path = APKSIGNER
                sign_args = [
                    "sign",
                    "--ks", KEYSTORE,
                    "--ks-key-alias", KEY_ALIAS,
                    "--ks-pass", f"pass:{KEY_PASS}",
                    "--key-pass", f"pass:{KEY_PASS}",
                    "--out", signed_apk,
                    rebuilt_apk
                ]
                cmd = ["cmd", "/c", bat_path] + sign_args
                env = os.environ.copy()
                env["JAVA_HOME"] = os.path.abspath("openjdk-21.0.7.6-hotspot")
                env["PATH"] = os.path.dirname(JAVA_BIN) + os.pathsep + env.get("PATH", "")
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                logging.info(f"Comando de firma: {' '.join(cmd)}")
            else:
                cmd = [JAVA_BIN, "-Xmx4g", "-jar", APKSIGNER, "sign", "--ks", KEYSTORE, "--ks-key-alias", KEY_ALIAS, "--ks-pass", f"pass:{KEY_PASS}", "--key-pass", f"pass:{KEY_PASS}", "--out", signed_apk, rebuilt_apk]
                result = subprocess.run(cmd, capture_output=True, text=True)
                logging.info(f"Comando de firma: {' '.join(cmd)}")
            if result.returncode != 0:
                play_sound("error.wav")
                error_msg = f"¡Error al firmar!\nCódigo de retorno: {result.returncode}\nError: {result.stderr}"
                ui_updater.show_error("Error", error_msg)
                ui_updater.set_status("Error al firmar")
                ui_updater.enable_btn()
                return
            ui_updater.step_progress(10)
            if not os.path.exists(signed_apk):
                play_sound("error.wav")
                ui_updater.show_error("Error", "¡APK firmado no fue creado!")
                ui_updater.set_status("APK firmado ausente")
                ui_updater.enable_btn()
                return
            try:
                with zipfile.ZipFile(signed_apk, 'r') as zf:
                    test = zf.testzip()
                    if test is not None:
                        raise Exception(f"Archivo APK dañado: {test}")
            except Exception as e:
                play_sound("error.wav")
                ui_updater.show_error("Error", f"Fallo al verificar la integridad del APK firmado: {e}")
                ui_updater.set_status("Fallo en la verificación del APK")
                ui_updater.enable_btn()
                return
            ui_updater.set_status("¡Listo!")
            play_sound("finish.wav")
            ui_updater.show_info("Éxito", f"¡Empaquetado APK completado!\nArchivo: {signed_apk}")
            ui_updater.enable_btn()
            try:
                output_dir = os.path.abspath("output")
                subprocess.Popen(f'explorer "{output_dir}"')
            except Exception as e:
                logging.warning(f"No se pudo abrir la carpeta output: {e}")
            for fname in os.listdir(OUTPUT_DIR):
                if not fname.endswith(".apk"):
                    fpath = os.path.join(OUTPUT_DIR, fname)
                    try:
                        if os.path.isdir(fpath):
                            shutil.rmtree(fpath)
                        else:
                            os.remove(fpath)
                    except Exception as e:
                        logging.warning(f"No se pudo eliminar el archivo temporal: {fpath}, {e}")
    except Exception as e:
        for d in tmpdirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        logging.exception("Error durante el empaquetado")
        ui_updater.set_status("Ocurrió un error")
        play_sound("error.wav")
        ui_updater.show_error("Error", str(e))
        ui_updater.enable_btn()
    finally:
        if original_java_home is not None:
            os.environ['JAVA_HOME'] = original_java_home
        else:
            os.environ.pop('JAVA_HOME', None)
        if original_path is not None:
            os.environ['PATH'] = original_path

def main():
    root = tk.Tk()
    root.title("Herramientas Kiridroid")
    root.geometry("700x420")
    try:
        root.iconbitmap(os.path.abspath("icon.ico"))
    except Exception as e:
        print(f"[Aviso] No se pudo establecer el icono de la ventana: {e}")
    style = ttk.Style()
    style.theme_use('default')
    style.configure('Rounded.TButton',
                    font=('Segoe UI', 12),
                    borderwidth=0,
                    relief="flat",
                    foreground="#fff",
                    background="#4CAF50",
                    padding=6)
    style.map('Rounded.TButton',
              background=[('active', '#45a049')])
    style.configure('Gray.TButton',
                    font=('Segoe UI', 10),
                    borderwidth=0,
                    relief="flat",
                    foreground="#fff",
                    background="#888888",
                    padding=4)
    style.map('Gray.TButton',
              background=[('active', '#666666')])
    main_frame = tk.Frame(root)
    main_frame.pack(padx=20, pady=20, fill="both", expand=True)
    tk.Label(main_frame, text="Seleccione la carpeta del juego:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=5)
    game_var = tk.StringVar()
    tk.Entry(main_frame, textvariable=game_var, width=40, font=("Segoe UI", 10)).grid(row=0, column=1, sticky="ew", pady=5)
    def browse_game():
        threading.Thread(target=play_sound, args=("file.wav",), daemon=True).start()
        path = filedialog.askdirectory()
        if path:
            game_var.set(path)
    ttk.Button(main_frame, text="Buscar", style='Gray.TButton', command=browse_game).grid(row=0, column=2, padx=5, pady=5)
    tk.Label(main_frame, text="Seleccione el archivo de icono:", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=5)
    icon_var = tk.StringVar()
    tk.Entry(main_frame, textvariable=icon_var, width=40, font=("Segoe UI", 10)).grid(row=1, column=1, sticky="ew", pady=5)
    def browse_icon():
        threading.Thread(target=play_sound, args=("file.wav",), daemon=True).start()
        path = filedialog.askopenfilename(filetypes=[("Archivos PNG", "*.png")])
        if path:
            icon_var.set(path)
    ttk.Button(main_frame, text="Buscar", style='Gray.TButton', command=browse_icon).grid(row=1, column=2, padx=5, pady=5)
    tk.Label(main_frame, text="Nombre del paquete:", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=5)
    pkg_var = tk.StringVar()
    tk.Entry(main_frame, textvariable=pkg_var, width=40, font=("Segoe UI", 10)).grid(row=2, column=1, sticky="ew", pady=5)
    tk.Label(main_frame, text="Nombre de la aplicación:", font=("Segoe UI", 10)).grid(row=3, column=0, sticky="w", pady=5)
    app_var = tk.StringVar()
    tk.Entry(main_frame, textvariable=app_var, width=40, font=("Segoe UI", 10)).grid(row=3, column=1, sticky="ew", pady=5)
    tk.Label(main_frame, text="Verifique la carpeta output para el resultado.", font=("Segoe UI", 10)).grid(row=4, column=0, columnspan=3, sticky="w", pady=10)
    progress = ttk.Progressbar(main_frame, length=500, mode='determinate', maximum=100)
    progress.grid(row=5, column=0, columnspan=3, pady=10, sticky="ew")
    status = tk.StringVar()
    status.set("")
    tk.Label(main_frame, textvariable=status, fg="#4CAF50", font=("Segoe UI", 11)).grid(row=6, column=0, columnspan=3, sticky="w", pady=5)
    version = check_apktool_version()
    tk.Label(main_frame, text=f"Versión de apktool: {version}", fg="#888888").grid(row=7, column=2, sticky="e", pady=5)
    start_btn = ttk.Button(main_frame, text="Iniciar", style='Rounded.TButton', width=15)
    start_btn.grid(row=8, column=1, pady=15)
    ui_updater = UIUpdater(root, progress, status, start_btn)
    def start_build():
        threading.Thread(target=play_sound, args=("trans.wav",), daemon=True).start()
        game_dir = game_var.get()
        icon_path = icon_var.get()
        package_name = pkg_var.get()
        app_name = app_var.get()
        if not (game_dir and icon_path and package_name and app_name):
            play_sound("error.wav")
            messagebox.showerror("Error", "¡Por favor, complete toda la información requerida!")
            return
        progress['value'] = 0
        status.set("Empaquetado iniciado...")
        ui_updater.disable_btn()
        t = threading.Thread(target=build_apk_thread, args=(game_dir, icon_path, package_name, app_name, ui_updater), daemon=True)
        t.start()
    start_btn.config(command=start_build)
    root.mainloop()

if __name__ == "__main__":
    main() 