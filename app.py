from flask import Flask, send_file, request    
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
import requests
import threading
import time

app = Flask(__name__)

# ==============================
# Funções utilitárias
# ==============================

def get_ema_image():
    local_path = os.path.join("images", "hud_battle.png")
    try:
        return Image.open(local_path).convert("RGBA")
    except Exception as e:
        print(f"Erro ao carregar hud_battle.png: {e}")
        return None

def get_background_image():
    local_path = os.path.join("images", "backbattle.jpg")
    try:
        return Image.open(local_path).convert("RGBA")
    except Exception as e:
        print(f"Erro ao carregar backbattle.jpg: {e}")
        return Image.new('RGBA', (960, 480), (255, 255, 255, 255)) 

def resize_image(image, target_height=96):
    ratio = target_height / float(image.size[1])
    width = int(float(image.size[0]) * ratio)
    return image.resize((width, target_height), Image.BICUBIC)

def get_real_pokemon_name(pokemon_identifier):
    # Pega nome oficial pela PokéAPI
    if str(pokemon_identifier).isdigit():
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_identifier}"
        response = requests.get(url)
        if response.status_code == 200:
            name = response.json()['name']
        else:
            name = str(pokemon_identifier)
    else:
        name = str(pokemon_identifier)

    # Tratamento especial para Megas
    if "-mega" in name:
        base_name = name.replace("-mega", "").capitalize()
        return f"M. {base_name}"
    return name.capitalize()

def get_pokemon_sprite(pokemon_name, is_pokemon1=False, shiny=False, target_height=96):
    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}"
    response = requests.get(url)

    if response.status_code != 200:
        return None

    data = response.json()

    # Seleção do sprite com fallback para Megas
    if is_pokemon1:  # Pokémon do player → normalmente costas
        sprite_key = 'back_shiny' if shiny else 'back_default'
        fallback_key = 'front_shiny' if shiny else 'front_default'
    else:  # Pokémon inimigo → frente
        sprite_key = 'front_shiny' if shiny else 'front_default'
        fallback_key = None
     
    sprite_url = data.get('sprites', {}).get(sprite_key)

    # Se não tiver sprite de costas → usa frente
    if not sprite_url and fallback_key:
        sprite_url = data.get('sprites', {}).get(fallback_key)

    if not sprite_url:
        return None

    sprite_response = requests.get(sprite_url)
    if sprite_response.status_code == 200:
        sprite = Image.open(BytesIO(sprite_response.content)).convert("RGBA")
        return resize_image(sprite, target_height=target_height)
    return None

# ==============================
# Funções para HP
# ==============================

def get_hp_image(color):
    local_path = os.path.join("images", f"overlay_{color}.jpg")
    try:
        return Image.open(local_path).convert("RGBA")
    except Exception as e:
        print(f"Erro ao carregar {local_path}: {e}")
        return None

def choose_hp_color(hp_ratio):
    if hp_ratio > 0.5:
        return "green"
    elif hp_ratio > 0.2:
        return "orange"
    else:
        return "red"

def draw_hp_bar(battle_image, position, hp_ratio):
    color = choose_hp_color(hp_ratio)
    hp_img = get_hp_image(color)
    if not hp_img:
        return

    bar_width = int(hp_img.width * hp_ratio)
    if bar_width <= 0:
        return

    cropped = hp_img.crop((0, 0, bar_width, hp_img.height))
    battle_image.paste(cropped, position, cropped)

# =============================
# Função principal de render
# =============================

def create_battle_image(pokemon1, pokemon2, sprite_height=96, hp_bar_scale=1.0, font_scale=5.0):
    shiny1 = request.args.get('shiny1', 'false').lower() == 'true'
    shiny2 = request.args.get('shiny2', 'false').lower() == 'true'

    sprite1 = get_pokemon_sprite(pokemon1, is_pokemon1=True, shiny=shiny1, target_height=sprite_height * 2)
    sprite2 = get_pokemon_sprite(pokemon2, is_pokemon1=False, shiny=shiny2, target_height=sprite_height * 2)
    if sprite1 is None or sprite2 is None:
        return None

    background = get_background_image()
    battle_image = Image.new('RGBA', background.size, (255, 255, 255, 0))
    battle_image.paste(background, (0, 0))

    # HP ratios
    hp1 = int(request.args.get('hp1', 100))
    hp2 = int(request.args.get('hp2', 100))
    hp1_ratio = max(0, min(1, hp1 / 100))
    hp2_ratio = max(0, min(1, hp2 / 100))

    # barras de HP primeiro (ficam "por baixo" da HUD)
    draw_hp_bar(battle_image, (55, 38), hp2_ratio)
    draw_hp_bar(battle_image, (190, 128), hp1_ratio)

    # HUD por cima das barras
    ema_image = get_ema_image()
    if ema_image:
        battle_image.paste(ema_image, (0, 0), ema_image)

    # sprites
    battle_image.paste(sprite1, (20, 75), sprite1)
    battle_image.paste(sprite2, (140, 10), sprite2)

    draw = ImageDraw.Draw(battle_image)
    _apply_effects(draw, battle_image)
    _draw_texts(draw, battle_image, pokemon1, pokemon2, font_scale)

    output = BytesIO()
    battle_image.save(output, format='PNG')
    output.seek(0)
    return output

def _apply_effects(draw, battle_image):
    def paste_if_exists(filename, position, size):
        if not filename:
            return
        path = os.path.join("images", f"{filename}.png")
        if os.path.exists(path):
            try:
                effect = Image.open(path).convert("RGBA")
                effect = effect.resize((size, size), Image.BICUBIC)
                battle_image.paste(effect, position, effect)
            except Exception as e:
                print(f"Erro ao carregar {filename}: {e}")

    # efeitos
    paste_if_exists(request.args.get('effect1'), (168, 132), 12)
    paste_if_exists(request.args.get('effect2'), (106, 22), 12)
    paste_if_exists(request.args.get('effect3'), (65, 25), 14)

    paste_if_exists(request.args.get('effect4'), (208, 116), 11)
    paste_if_exists(request.args.get('effect5'), (65, 24), 11)

    # pokébolas
    positions_p2 = [(2, 50)]
    positions_p1 = [(240, 152)]

    paste_if_exists(request.args.get('ball1'), positions_p1[0], 15)  # jogador
    paste_if_exists(request.args.get('ball2'), positions_p2[0], 15)  # inimigo

def _draw_texts(draw, battle_image, pokemon1, pokemon2, font_scale):
    try:
        font = ImageFont.truetype("pokemon-ds-font.ttf", int(2.2 * font_scale))  # nomes e levels
        font_turn = ImageFont.truetype("pokemon-ds-font.ttf", int(2.6 * font_scale))  # turno
    except IOError:
        font = font_turn = ImageFont.load_default()

    battle_turn = request.args.get('turn', '1')
    draw.text((203, 133), f"{battle_turn}", fill=(40, 40, 40), font=font_turn)

    real_pokemon1 = get_real_pokemon_name(pokemon1)
    real_pokemon2 = get_real_pokemon_name(pokemon2)

    level1 = request.args.get('level1', '1')
    level2 = request.args.get('level2', '1')

    # Pokémon 2 (inimigo - topo esquerdo)
    draw.text((5, 23), real_pokemon2, fill=(0, 0, 0), font=font)
    draw.text((93, 23), f"{level2}", fill=(0, 0, 0), font=font)

    # Pokémon 1 (player - canto inferior)
    bbox1 = draw.textbbox((0, 0), real_pokemon1, font=font)
    text_width1 = bbox1[2] - bbox1[0]
    x = 178 - text_width1 // 2
    draw.text((x, 115), real_pokemon1, fill=(0, 0, 0), font=font)
    draw.text((235, 115), f"{level1}", fill=(0, 0, 0), font=font)

# ==============================
# Rotas Flask
# ==============================

@app.route('/battle', methods=['GET'])
def battle():
    pokemon1 = request.args.get('pokemon1')
    pokemon2 = request.args.get('pokemon2')
    if not pokemon1 or not pokemon2:
        return "Please provide both pokemon1 and pokemon2 parameters.", 400

    sprite_height = int(request.args.get('sprite_height', 55))
    hp_bar_scale = float(request.args.get('hp_bar_scale', 1.5))
    font_scale = float(request.args.get('font_scale', 6.0))

    battle_image = create_battle_image(pokemon1, pokemon2, sprite_height, hp_bar_scale, font_scale)
    if battle_image is None:
        return "Failed to retrieve one or both Pokémon sprites.", 400
    return send_file(battle_image, mimetype='image/png')

# ==============================
# Auto Ping
# ==============================

def auto_ping():
    url = "https://apiduckie.onrender.com/battle?pokemon1=4&pokemon2=1&hp1=80&hp2=65&level1=100&level2=100&shiny1=true&shiny2=true"
    while True:
        try:
            response = requests.get(url)
            now = time.strftime("%d/%m/%Y %H:%M:%S")
            print(f"[{now}] Ping enviado! Status code: {response.status_code}")
        except Exception as e:
            print(f"Erro ao enviar ping: {e}")
        time.sleep(300)

if __name__ == '__main__':
    threading.Thread(target=auto_ping, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
