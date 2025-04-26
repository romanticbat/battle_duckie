from flask import Flask, send_file, request
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
import requests

app = Flask(__name__)

def get_ema_image():
    local_path = os.path.join("images", "hpdesign_battle.png")
    try:
        ema_image = Image.open(local_path).convert("RGBA")
        return ema_image
    except Exception as e:
        print(f"Erro ao carregar a imagem local: {e}")
        return 

def get_background_image():
    local_path = os.path.join("images", "background_battle.jpg")
    try:
        background = Image.open(local_path).convert("RGBA")
        return background
    except Exception as e:
        print(f"Erro ao carregar a imagem de fundo local: {e}")
        return Image.new('RGBA', (960, 480), (255, 255, 255, 255)) 

def get_pokemon_sprite(pokemon_name, is_pokemon1=False, shiny=False, target_height=96):
    """Busca o sprite do Pokémon."""
    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()

        if is_pokemon1:
            sprite_key = 'back_shiny' if shiny else 'back_default'
        else:
            sprite_key = 'front_shiny' if shiny else 'front_default'

        if 'sprites' in data and sprite_key in data['sprites']:
            sprite_url = data['sprites'][sprite_key]
            if sprite_url:
                sprite_response = requests.get(sprite_url)
                if sprite_response.status_code == 200:
                    sprite = Image.open(BytesIO(sprite_response.content)).convert("RGBA")
                    sprite = resize_image(sprite, target_height=target_height)
                    return sprite
    return None

def get_real_pokemon_name(pokemon_identifier):
    """Se for número, busca o nome real na API. Se for texto, usa direto."""
    if str(pokemon_identifier).isdigit():
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_identifier}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data['name']
        else:
            return str(pokemon_identifier)
    else:
        return str(pokemon_identifier)

def resize_image(image, target_height=96):
    """Redimensiona a imagem mantendo proporção."""
    ratio = target_height / float(image.size[1])
    width = int(float(image.size[0]) * ratio)
    image = image.resize((width, target_height), Image.BICUBIC)
    return image

def create_battle_image(pokemon1, pokemon2, sprite_height=96, hp_bar_scale=1.0, font_scale=5.0):
    shiny1 = request.args.get('shiny1', 'false').lower() == 'true'
    shiny2 = request.args.get('shiny2', 'false').lower() == 'true'

    # pega sprites
    sprite1 = get_pokemon_sprite(pokemon1, is_pokemon1=True, shiny=shiny1, target_height=sprite_height * 2)
    sprite2 = get_pokemon_sprite(pokemon2, is_pokemon1=False, shiny=shiny2, target_height=sprite_height * 2)

    if sprite1 is None or sprite2 is None:
        return None

    background = get_background_image()
    background = resize_image(background, target_height=480)
    battle_image = Image.new('RGBA', background.size, (255, 255, 255, 0))
    battle_image.paste(background, (0, 0))

    battle_image.paste(sprite1, (165, 245), sprite1)
    battle_image.paste(sprite2, (530, 110), sprite2)

    draw = ImageDraw.Draw(battle_image)

    hp_bar_width = int(100 * hp_bar_scale)
    hp_bar_height = int(9 * hp_bar_scale)

    pokemon1_hp_bar_position = (70, 230)
    pokemon2_hp_bar_position = (739, 230)

    hp1 = int(request.args.get('hp1', 100))
    hp2 = int(request.args.get('hp2', 100))
    hp1_ratio = float(hp1) / 100
    hp2_ratio = float(hp2) / 100

    hp_bar_color1 = (0, 255, 0) if hp1_ratio > 0.5 else (255, 165, 0) if hp1_ratio > 0.2 else (255, 0, 0)
    hp_bar_color2 = (0, 255, 0) if hp2_ratio > 0.5 else (255, 165, 0) if hp2_ratio > 0.2 else (255, 0, 0)

    draw.rectangle((pokemon1_hp_bar_position[0], pokemon1_hp_bar_position[1],
                    pokemon1_hp_bar_position[0] + int(hp_bar_width * hp1_ratio), pokemon1_hp_bar_position[1] + hp_bar_height),
                   fill=hp_bar_color1)
    draw.rectangle((pokemon2_hp_bar_position[0] + int(hp_bar_width * (1 - hp2_ratio)), pokemon2_hp_bar_position[1],
                    pokemon2_hp_bar_position[0] + hp_bar_width, pokemon2_hp_bar_position[1] + hp_bar_height),
                   fill=hp_bar_color2)

    ema_image = get_ema_image()
    if ema_image:
        battle_image.paste(ema_image, (0, 15), ema_image)

    # Efeitos locais
    battle_effect_pokemon2_name = request.args.get('battle_effect_pokemon2')
    if battle_effect_pokemon2_name:
        effect_path = os.path.join("images", f"{battle_effect_pokemon2_name}.png")
        if os.path.exists(effect_path):
            try:
                battle_effect_pokemon2 = Image.open(effect_path).convert("RGBA")
                battle_image.paste(battle_effect_pokemon2, (900, 198), battle_effect_pokemon2)
            except Exception as e:
                print(f"Erro ao carregar efeito do Pokémon 2: {e}")

    battle_effect_battle_name = request.args.get('battle_effect_battle')
    if battle_effect_battle_name:
        effect_path = os.path.join("images", f"{battle_effect_battle_name}.png")
        if os.path.exists(effect_path):
            try:
                battle_effect_battle = Image.open(effect_path).convert("RGBA")
                battle_image.paste(battle_effect_battle, (65, 25), battle_effect_battle)
            except Exception as e:
                print(f"Erro ao carregar efeito da batalha: {e}")

    # Nome e level dos pokémons
    font_size = int(2.2 * font_scale)
    try:
        font = ImageFont.truetype("pokemonfont.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    pokemon1_level = request.args.get('level1', '1')
    pokemon2_level = request.args.get('level2', '1')

    real_pokemon1_name = get_real_pokemon_name(pokemon1)
    real_pokemon2_name = get_real_pokemon_name(pokemon2)

    draw.text((5, 208), f"{real_pokemon1_name.capitalize()}", fill=(255, 255, 255), font=font)
    draw.text((194, 211), f"{pokemon1_level}", fill=(255, 255, 255), font=font)

    draw.text((868, 208), f"{real_pokemon2_name.capitalize()}", fill=(255, 255, 255), font=font)
    draw.text((770, 211), f"{pokemon2_level}", fill=(255, 255, 255), font=font)

    output = BytesIO()
    battle_image.save(output, format='PNG')
    output.seek(0)
    return output

@app.route('/battle', methods=['GET'])
def battle():
    pokemon1 = request.args.get('pokemon1')
    pokemon2 = request.args.get('pokemon2')
    sprite_height = int(request.args.get('sprite_height', 96))
    hp_bar_scale = float(request.args.get('hp_bar_scale', 1.5))
    font_scale = float(request.args.get('font_scale', 8.0))

    if not pokemon1 or not pokemon2:
        return "Please provide both pokemon1 and pokemon2 parameters.", 400

    battle_image = create_battle_image(pokemon1, pokemon2, sprite_height, hp_bar_scale, font_scale)
    if battle_image is None:
        return "Failed to retrieve one or both Pokémon sprites.", 400

    return send_file(battle_image, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
