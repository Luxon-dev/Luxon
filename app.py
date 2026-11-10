import ast
import base64
import json
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog

HTML_FILE = "index.html"
# 🔑 CLAVE DE DESARROLLADOR (Podés cambiarla por la que prefieras entre las comillas)
DEV_PASSWORD = "luxon2026"

def clean_js_to_json(js_str):
    """Convierte un arreglo de objetos JS a JSON válido."""
    json_str = re.sub(r'([{\s,])([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_str)
    json_str = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', json_str)
    return json_str

def load_products_from_html():
    try:
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        match = re.search(r"const\s+products\s*=\s*(\[.*?\]);", content, re.DOTALL)
        if not match:
            print("❌ No se encontró el arreglo 'const products = [...]' en el HTML.")
            sys.exit(1)
            
        raw_js_array = match.group(1)
        valid_json_str = clean_js_to_json(raw_js_array)
        
        try:
            products = json.loads(valid_json_str)
        except json.JSONDecodeError as jde:
            print(f"⚠️ Error al parsear los productos: {jde.msg} (Línea {jde.lineno})")
            sys.exit(1)

        return content, match.group(0), products
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo '{HTML_FILE}'. Asegurate de ejecutarlo en la misma carpeta.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al leer productos: {e}")
        sys.exit(1)

def save_products_to_html(original_content, old_match_str, products):
    formatted_json = json.dumps(products, indent=12, ensure_ascii=False)
    new_products_block = f"const products = {formatted_json};"
    new_content = original_content.replace(old_match_str, new_products_block)
    
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("\n✅ ¡El catálogo en 'index.html' se actualizó con éxito!")

def generate_next_id(products):
    """Genera automáticamente el siguiente ID correlativo"""
    max_num = 0
    for p in products:
        p_id = p.get("id", "")
        match = re.search(r'LUX-(\d+)', p_id)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return f"LUX-{max_num + 1:03d}"

def select_images_to_base64():
    """Abre la ventana de Windows para seleccionar fotos de la PC y pasarlas a Base64"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    file_paths = filedialog.askopenfilenames(
        title="Seleccioná una o varias fotos del producto",
        filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp")]
    )
    
    base64_images = []
    for path in file_paths:
        try:
            ext = path.split('.')[-1].lower()
            mime_type = "image/jpeg" if ext in ['jpg', 'jpeg'] else "image/png"
            if ext == 'webp': mime_type = "image/webp"
                
            with open(path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                data_uri = f"data:{mime_type};base64,{encoded_string}"
                base64_images.append(data_uri)
        except Exception as e:
            print(f"⚠️ No se pudo procesar la imagen {path}: {e}")
            
    return base64_images

def verify_dev_access():
    """Verifica la contraseña para acceder a funciones de Desarrollador"""
    print("\n🔒 ESTA ACCIÓN REQUIERE MODO DESARROLLADOR")
    pwd = input("Ingresá la clave secreta: ").strip()
    if pwd == DEV_PASSWORD:
        print("🔓 ¡Clave correcta! Acceso concedido.")
        return True
    else:
        print("❌ Clave incorrecta. Operación cancelada.")
        return False

def show_menu():
    print("\n==============================================")
    print("      ADMINISTRADOR DE CATÁLOGO LUXON         ")
    print("==============================================")
    print("1. Ver lista de productos")
    print("2. Agregar un nuevo producto (Libre)")
    print("3. Editar producto (Precios, nombres, fotos, etc.)")
    print("4. [DEV] Editar ID de un producto (Requiere Clave)")
    print("5. Eliminar un producto")
    print("6. Salir")
    return input("\nSeleccioná una opción (1-6): ").strip()

def list_products(products):
    print("\n------------------- CATÁLOGO ACTUAL -------------------")
    for i, p in enumerate(products, 1):
        variantes = ", ".join(p.get("variants", ["Sin variantes"]))
        print(f"{i}. ID: [{p['id']}] | {p['title']} - {p['price']} ({p['category'].upper()})")
        print(f"   Variantes: {variantes} | Fotos: {len(p.get('images', []))}")
        print("------------------------------------------------------")

def add_product(products):
    print("\n--- AGREGAR NUEVO PRODUCTO ---")
    p_id = generate_next_id(products)
    print(f"🤖 ID asignado automáticamente por el sistema: {p_id}")
    
    title = input("Nombre del Producto: ").strip()
    if not title:
        print("❌ El nombre no puede estar vacío.")
        return False
    
    print("\nCategorías disponibles: accesorios | hogar | cuidado")
    category = input("Categoría [accesorios]: ").strip().lower() or "accesorios"
    
    try:
        numeric_price = int(input("Precio numérico (ej: 45000): ").strip() or "0")
    except ValueError:
        numeric_price = 0
    formatted_price = f"${numeric_price:,.0f}".replace(",", ".")
    
    badge = input("Etiqueta / Badge (ej: Nuevo, Más Vendido, Exclusivo): ").strip() or "Exclusivo"
    description = input("Descripción corta: ").strip()
    
    print("\n📸 Seleccioná las fotos desde tu computadora...")
    images = select_images_to_base64()
    
    if not images:
        images = ["https://placehold.co/600x600/EAE0D5/222222?text=LuXon"]
    
    print("\nIngresá los Colores / Variantes separados por coma (ej: Dorado, Plata, Negro):")
    vars_str = input("Variantes [Único]: ").strip()
    variants = [v.strip() for v in vars_str.split(",") if v.strip()]
    if not variants:
        variants = ["Único"]

    new_prod = {
        "id": p_id,
        "title": title,
        "category": category,
        "price": formatted_price,
        "numericPrice": numeric_price,
        "badge": badge,
        "badgeColor": "bg-gold-400 text-charcoal",
        "variants": variants,
        "images": images,
        "description": description
    }
    
    products.append(new_prod)
    return True

def edit_product(products):
    list_products(products)
    p_id = input("\nIngresá el ID del producto que querés editar: ").strip().upper()
    prod = next((p for p in products if p['id'] == p_id), None)
    
    if not prod:
        print("❌ Producto no encontrado.")
        return False
        
    print(f"\nEditando: {prod['title']} (Presioná ENTER si querés mantener el valor actual)")
    
    new_title = input(f"Nombre [{prod['title']}]: ").strip()
    if new_title: prod['title'] = new_title
    
    new_cat = input(f"Categoría [{prod['category']}]: ").strip().lower()
    if new_cat: prod['category'] = new_cat
    
    new_num_price = input(f"Precio Numérico [{prod['numericPrice']}]: ").strip()
    if new_num_price:
        try:
            prod['numericPrice'] = int(new_num_price)
            prod['price'] = f"${prod['numericPrice']:,.0f}".replace(",", ".")
        except ValueError:
            pass
        
    new_badge = input(f"Etiqueta / Badge [{prod['badge']}]: ").strip()
    if new_badge: prod['badge'] = new_badge
    
    new_desc = input(f"Descripción [{prod['description']}]: ").strip()
    if new_desc: prod['description'] = new_desc
    
    curr_vars = ", ".join(prod.get('variants', []))
    new_vars = input(f"Variantes [{curr_vars}]: ").strip()
    if new_vars:
        prod['variants'] = [v.strip() for v in new_vars.split(",") if v.strip()]
        
    cambiar_fotos = input("¿Querés elegir nuevas fotos desde tu PC? (s/n): ").strip().lower()
    if cambiar_fotos == 's':
        nuevas_imgs = select_images_to_base64()
        if nuevas_imgs:
            prod['images'] = nuevas_imgs
            print("✅ Fotos actualizadas.")
        
    return True

def edit_product_id(products):
    """Función exclusiva de Desarrollador para modificar IDs internos"""
    if not verify_dev_access():
        return False
        
    list_products(products)
    p_id = input("\nIngresá el ID ACTUAL del producto que querés cambiar: ").strip().upper()
    prod = next((p for p in products if p['id'] == p_id), None)
    
    if not prod:
        print("❌ Producto no encontrado.")
        return False
        
    print(f"Producto seleccionado: {prod['title']} (ID actual: {prod['id']})")
    new_id = input("Ingresá el NUEVO ID único (ej: LUX-010): ").strip().upper()
    
    if not new_id:
        print("❌ El ID no puede estar vacío.")
        return False
        
    if any(p['id'] == new_id for p in products):
        print("❌ Error: Ya existe otro producto con ese ID.")
        return False
        
    prod['id'] = new_id
    print(f"✅ ¡ID modificado con éxito a {new_id}!")
    return True

def delete_product(products):
    list_products(products)
    p_id = input("\nIngresá el ID del producto a ELIMINAR: ").strip().upper()
    prod = next((p for p in products if p['id'] == p_id), None)
    
    if not prod:
        print("❌ Producto no encontrado.")
        return False
        
    confirm = input(f"⚠️ ¿Seguro que querés eliminar '{prod['title']}' ({p_id})? (s/n): ").strip().lower()
    if confirm == 's':
        products.remove(prod)
        print(f"🗑️ Producto {p_id} eliminado.")
        return True
    return False

def main():
    while True:
        content, match_str, products = load_products_from_html()
        opt = show_menu()
        
        if opt == "1":
            list_products(products)
        elif opt == "2":
            if add_product(products):
                save_products_to_html(content, match_str, products)
        elif opt == "3":
            if edit_product(products):
                save_products_to_html(content, match_str, products)
        elif opt == "4":
            if edit_product_id(products):
                save_products_to_html(content, match_str, products)
        elif opt == "5":
            if delete_product(products):
                save_products_to_html(content, match_str, products)
        elif opt == "6":
            print("\n¡Hasta luego!")
            break
        else:
            print("Opción inválida.")

if __name__ == "__main__":
    main()