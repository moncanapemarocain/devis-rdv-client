"""
Application Streamlit pour générer des devis de canapés sur mesure
Compatible Streamlit Cloud - Utilise canapematplot.py
"""

import streamlit as st
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from png_generator import generer_png_devis

# Import complet du module canapematplot pour pouvoir désactiver certains
# dessins (flèches et étiquettes) lorsque l'on souhaite enlever les
# dimensions du schéma.  On importe le module complet afin de pouvoir
# modifier temporairement ses fonctions internes avant de générer le
# schéma.
import canapematplot

def overlay_dimension_text(image: Image.Image, type_canape: str, tx: int | None, ty: int | None, tz: int | None, profondeur: int | None, angle: int) -> Image.Image:
    """
    Ajoute une légende des dimensions (par exemple « 200 x 90 cm ») autour
    de l'image du canapé.  La légende est pivotée du même angle que le
    schéma afin de conserver la cohérence visuelle.  Si l'angle est 0 ou
    180 degrés, la légende est placée en dessous du schéma ; pour 90
    degrés, elle est placée à droite ; et pour 270 degrés, à gauche.

    Parameters
    ----------
    image : PIL.Image
        Image du schéma déjà pivotée si nécessaire.
    type_canape : str
        Libellé du type de canapé (ex : "Simple", "L - Sans Angle", etc.).
    tx, ty, tz : int or None
        Longueurs des banquettes selon la configuration.
    profondeur : int
        Profondeur d'assise.
    angle : int
        Angle de rotation appliqué au schéma (0, 90, 180 ou 270).

    Returns
    -------
    PIL.Image
        Nouvelle image avec la légende ajoutée.
    """
    # Déterminer les dimensions à afficher selon le type de canapé
    dims: list[int] = []
    tc = type_canape or ""
    if "U" in tc:
        # Ordre d'affichage : profondeur de la partie de gauche (ty), longueur principale (tx), longueur droite (tz)
        dims = [d for d in (ty, tx, tz) if d]
    elif "L" in tc:
        # Canapé en L : deux longueurs
        dims = [d for d in (ty, tx) if d]
    else:
        # Canapé simple : longueur et profondeur d'assise
        dims = [d for d in (tx, profondeur) if d]
    # Construire la chaîne de dimensions (sans unité pour toutes sauf la dernière)
    if dims:
        # Exemple : [200, 90, 80] -> "200 x 90 x 80 cm"
        parts = [str(d) for d in dims]
        text = " x ".join(parts) + " cm"
    else:
        text = ""
    # Sélectionner une taille de police proportionnelle à la taille de l'image
    # pour que la légende reste lisible même après redimensionnement du PDF.
    try:
        # On utilise DejaVuSans s'il est disponible
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        base_size = max(14, int(min(image.width, image.height) * 0.04))
        font = ImageFont.truetype(font_path, base_size)
    except Exception:
        font = ImageFont.load_default()
    # Créer une image pour le texte et déterminer sa taille.
    # Pillow version 10 a supprimé la méthode `ImageDraw.textsize`. Pour une
    # compatibilité maximale, on tente d’utiliser `ImageDraw.textbbox` (Pillow ≥ 8.3)
    # ou bien `ImageFont.getsize`.  Si tout échoue, on retombe sur un calcul
    # approximatif.
    dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw_dummy = ImageDraw.Draw(dummy)
    try:
        # textbbox retourne (x0, y0, x1, y1)
        bbox = draw_dummy.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        # fallbacks selon la version de Pillow
        try:
            text_w, text_h = font.getsize(text)
        except Exception:
            try:
                # méthode textlength ne fournit que la largeur, estimons la hauteur
                text_w = draw_dummy.textlength(text, font=font)
                # hauteur approximative basée sur la taille de la police
                text_h = int(font.size * 1.2)
            except Exception:
                # Valeurs par défaut si aucune méthode n'est disponible
                text_w, text_h = 0, 0
    # Si le texte est vide, ne pas créer d'image
    if text_w > 0 and text_h > 0:
        text_img = Image.new("RGBA", (text_w, text_h), (255, 255, 255, 0))
        draw_text = ImageDraw.Draw(text_img)
        draw_text.text((0, 0), text, fill="black", font=font)
    else:
        # Aucun texte ou taille indéterminée, image transparente vide
        text_img = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    # Tourner la légende du même angle que l'image
    rotated_text = text_img.rotate(angle, expand=True)
    # Selon l'angle, on ajoute la légende en bas, à droite ou à gauche
    if angle % 360 in (0, 180):
        # légende horizontale en bas
        new_w = max(image.width, rotated_text.width)
        new_h = image.height + rotated_text.height
        new_img = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 0))
        # centrer le schéma horizontalement
        offset_x = (new_w - image.width) // 2
        new_img.paste(image, (offset_x, 0), image.convert("RGBA"))
        # centrer la légende horizontalement
        offset_tx = (new_w - rotated_text.width) // 2
        new_img.paste(rotated_text, (offset_tx, image.height), rotated_text)
    elif angle % 360 == 90:
        # légende verticale à droite
        new_w = image.width + rotated_text.width
        new_h = max(image.height, rotated_text.height)
        new_img = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 0))
        # centrer le schéma verticalement
        offset_y = (new_h - image.height) // 2
        new_img.paste(image, (0, offset_y), image.convert("RGBA"))
        # centrer la légende verticalement
        offset_ty = (new_h - rotated_text.height) // 2
        new_img.paste(rotated_text, (image.width, offset_ty), rotated_text)
    else:  # 270°
        # légende verticale à gauche
        new_w = image.width + rotated_text.width
        new_h = max(image.height, rotated_text.height)
        new_img = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 0))
        offset_y = (new_h - image.height) // 2
        new_img.paste(image, (rotated_text.width, offset_y), image.convert("RGBA"))
        offset_ty = (new_h - rotated_text.height) // 2
        new_img.paste(rotated_text, (0, offset_ty), rotated_text)
    return new_img.convert("RGB")
from typing import Optional, Dict

# Palette de couleurs personnalisable pour le rendu du schéma.
# La clef "Transparent (par défaut)" correspond à une absence de remplissage
# (les rectangles seront transparents). Les autres entrées sont converties
# en codes hexadécimaux lors du rendu.
COLOR_PALETTE: Dict[str, Optional[str]] = {
    # La première entrée correspond à la sélection « Blanc » par défaut.  L'ancienne entrée
    # « Transparent (par défaut) » est conservée comme option mais n'est plus utilisée comme valeur par défaut.
    "Blanc": "#ffffff",
    "Transparent": None,
    "Beige": "#d8c4a8",
    "Beige clair": "#e6dac8",
    "Crème": "#f4f1e9",
    "Taupe": "#8B7E74",
    "Gris foncé": "#7d7d7d",
    "Gris clair": "#cfcfcf",
    "Marron clair": "#a1866f",
}

# Import des modules personnalisés
# Import du nouveau module de pricing (avec angle traité comme banquette)
from pricing import calculer_prix_total
from pdf_generator import generer_pdf_devis

# Import des fonctions de génération de schémas
from canapematplot import (
    render_LNF, render_LF_variant, render_U2f_variant,
    render_U, render_U1F_v1, render_U1F_v2, render_U1F_v3, render_U1F_v4,
    render_Simple1
)

# --- SÉCURITÉ VISUELLE ---
# Cache le menu hamburger, le footer et l'en-tête par défaut
hide_streamlit_style = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* Cache l'option "Deploy" si jamais elle apparait */
    .stDeployButton {display:none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Configuration de la page
st.set_page_config(
    page_title="Configurateur Canapé Marocain",
    page_icon="🛋️",
    layout="wide"
)

# CSS personnalisé pour le design
st.markdown("""
<style>
    /* Fond principal */
    .stApp {
        background-color: #FBF6EF;
        /* Réduire la marge supérieure : seulement 20 % de la marge par défaut.  
           Nous appliquons un léger padding en haut pour conserver une fine bande d'espacement. */
        padding-top: 0.6rem;
        margin-top: 0;
    }

    /* Réduire également le padding du conteneur principal tout en conservant un léger espace */
    div.block-container {
        padding-top: 0.6rem;
    }
    
    /* Titres */
    h1, h2, h3 {
        color: #372E2B !important;
    }

    p {
        color: #8C6F63 !important;
    }
    
    /* Onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #EDE7DE;
        padding: 10px;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #EDE7DE;
        color: #8C6F63;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 500;
        border: none;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #FBF6EF !important;
        color: #8C6F63 !important;
        font-weight: 600;
    }
    
    /* Champs de saisie */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background-color: #EDE7DE !important;
        color: #8C6F63 !important;
        border: 1px solid #D5CFC6 !important;
        border-radius: 8px !important;
    }
    
    .stTextInput label, .stNumberInput label, .stSelectbox label {
        color: #8C6F63 !important;
        font-weight: 500;
    }

    div.st-an {
        background-color : red 
    }
    
    /* Checkbox */
    .stCheckbox label {
        color: #8C6F63 !important;
    }

    div.st-emotion-cache-1q82h82.e1wr3kle3 {
        color: black;
    }
    
    /* Boutons normaux */
    .stButton button {
        background-color: #EDE7DE !important;
        color: #8C6F63 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        background-color: #D5CFC6 !important;
        transform: translateY(-2px);
    }

    
    .stButton button[kind="primary"]:hover {
        background-color: #D5CFC6 !important;
    }
    
    /* Conteneurs */
    .stContainer {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    /* Messages */
    .stSuccess {
        background-color: #D4EDDA !important;
        color: #155724 !important;
        border-radius: 8px;
    }
    
    .stError {
        background-color: #F8D7DA !important;
        color: #721C24 !important;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)
def generer_schema_canape(
    type_canape,
    tx,
    ty,
    tz,
    profondeur,
    acc_left,
    acc_right,
    acc_bas,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side,
    meridienne_len,
    coussins="auto",
    nb_traversins_supp: int = 0,
    traversins_positions: list[str] | None = None,
    couleurs: Optional[Dict[str, Optional[str]]] = None,
) -> plt.Figure:
    """Génère le schéma du canapé.

    Parameters
    ----------
    type_canape : str
        Libellé du type de canapé (p. ex. "Simple (S)", "L - Sans Angle", etc.).
    tx, ty, tz : int or None
        Dimensions horizontales du canapé selon la configuration.
    profondeur : int
        Profondeur d'assise en centimètres.
    acc_left, acc_right, acc_bas : bool
        Indiquent la présence d'accoudoirs à gauche, à droite et en bas.
    dossier_left, dossier_bas, dossier_right : bool
        Indiquent la présence de dossiers sur les côtés.
    meridienne_side : str or None
        Côté de la méridienne ("g" ou "d"), ou None s'il n'y en a pas.
    meridienne_len : int
        Longueur de la méridienne en centimètres.
    coussins : str or int
        Mode d'optimisation des coussins ("auto", "65", "80", "80-90", "90", "valise", etc.).
    nb_traversins_supp : int, optional
        Nombre de traversins supplémentaires sélectionnés dans le formulaire. Si strictement positif,
        des traversins seront dessinés selon la géométrie du canapé.  Par défaut, aucun traversin
        n'est dessiné.

    Returns
    -------
    matplotlib.figure.Figure
        La figure générée représentant le canapé.
    """
    fig = plt.figure(figsize=(12, 8))

    # ------------------------------------------------------------------
    # Normalisation du paramètre « meridienne_side ».  Les fonctions de
    # canapefullv117 attendent des codes courts : « g » pour gauche,
    # « d » pour droite et « b » pour bas.  Le formulaire peut stocker
    # des valeurs dans différentes langues ou formats ; on convertit
    # systématiquement ici vers ces codes.  Si aucune méridienne
    # n'est définie (meridienne_side est falsy), on laisse la valeur à None.
    if meridienne_side:
        ms = str(meridienne_side).lower()
        mapping = {
            "left": "g", "gauche": "g", "g": "g",
            "right": "d", "droite": "d", "d": "d",
            "bas": "b", "bottom": "b", "b": "b"
        }
        meridienne_side = mapping.get(ms, ms)
    else:
        meridienne_side = None

    try:
        # Initialiser la configuration des traversins uniquement si au moins un traversin
        # supplémentaire est demandé.  Cela permet d'afficher les traversins sur le schéma
        # uniquement lorsque l'utilisateur l'a explicitement indiqué dans le formulaire.
        traversins_cfg: str | None = None
        # Si l'utilisateur a sélectionné explicitement des positions pour les traversins,
        # on les utilise pour le schéma.  Les valeurs possibles en entrée sont des
        # libellés en français ("Gauche", "Droite", "Bas"); on les convertit en
        # codes attendus par canapematplot/canapefullv88 : g, d, b.
        if traversins_positions:
            mapping = {
                "gauche": "g",
                "droite": "d",
                "bas": "b",
                "Gauche": "g",
                "Droite": "d",
                "Bas": "b",
            }
            codes = []
            for pos in traversins_positions:
                key = pos.strip().lower()
                if key in mapping:
                    codes.append(mapping[key])
            # On trie et on supprime les doublons pour former la chaîne
            if codes:
                traversins_cfg = ",".join(sorted(set(codes)))
        elif nb_traversins_supp and nb_traversins_supp > 0:
            # Déterminer la configuration par défaut en fonction du type de canapé.
            if "Simple" in type_canape:
                traversins_cfg = "g,d"
            elif "L" in type_canape:
                traversins_cfg = "g,b"
            elif "U" in type_canape:
                traversins_cfg = "g,b,d"

        # Choisir la fonction de rendu appropriée en fonction du type de canapé.
        if "Simple" in type_canape:
            render_Simple1(
                tx=tx,
                profondeur=profondeur,
                dossier=dossier_bas,
                acc_left=acc_left,
                acc_right=acc_right,
                meridienne_side=meridienne_side,
                meridienne_len=meridienne_len,
                coussins=coussins,
                traversins=traversins_cfg,
                couleurs=couleurs,
                window_title="Canapé Simple",
            )
        elif "L - Sans Angle" in type_canape:
            render_LNF(
                tx=tx,
                ty=ty,
                profondeur=profondeur,
                dossier_left=dossier_left,
                dossier_bas=dossier_bas,
                acc_left=acc_left,
                acc_bas=acc_bas,
                meridienne_side=meridienne_side,
                meridienne_len=meridienne_len,
                coussins=coussins,
                traversins=traversins_cfg,
                variant="auto",
                couleurs=couleurs,
                window_title="Canapé L - Sans Angle",
            )
        elif "L - Avec Angle" in type_canape:
            render_LF_variant(
                tx=tx,
                ty=ty,
                profondeur=profondeur,
                dossier_left=dossier_left,
                dossier_bas=dossier_bas,
                acc_left=acc_left,
                acc_bas=acc_bas,
                meridienne_side=meridienne_side,
                meridienne_len=meridienne_len,
                coussins=coussins,
                traversins=traversins_cfg,
                couleurs=couleurs,
                window_title="Canapé L - Avec Angle",
            )
        elif "U - Sans Angle" in type_canape:
            # Pour un canapé en U sans angle, transmettre également les
            # paramètres de méridienne afin d'afficher correctement cette
            # extension sur le schéma si elle est définie.
            render_U(
                tx=tx,
                ty_left=ty,
                tz_right=tz,
                profondeur=profondeur,
                dossier_left=dossier_left,
                dossier_bas=dossier_bas,
                dossier_right=dossier_right,
                acc_left=acc_left,
                acc_bas=acc_bas,
                acc_right=acc_right,
                coussins=coussins,
                traversins=traversins_cfg,
                variant="auto",
                couleurs=couleurs,
                window_title="Canapé U - Sans Angle",
                meridienne_side=meridienne_side,
                meridienne_len=meridienne_len,
            )
        elif "U - 1 Angle" in type_canape:
            render_U1F_v1(
                tx=tx,
                ty=ty,
                tz=tz,
                profondeur=profondeur,
                dossier_left=dossier_left,
                dossier_bas=dossier_bas,
                dossier_right=dossier_right,
                acc_left=acc_left,
                acc_right=acc_right,
                meridienne_side=meridienne_side,
                meridienne_len=meridienne_len,
                coussins=coussins,
                traversins=traversins_cfg,
                couleurs=couleurs,
                window_title="Canapé U - 1 Angle",
            )
        elif "U - 2 Angles" in type_canape:
            render_U2f_variant(
                tx=tx,
                ty_left=ty,
                tz_right=tz,
                profondeur=profondeur,
                dossier_left=dossier_left,
                dossier_bas=dossier_bas,
                dossier_right=dossier_right,
                acc_left=acc_left,
                acc_bas=acc_bas,
                acc_right=acc_right,
                meridienne_side=meridienne_side,
                meridienne_len=meridienne_len,
                coussins=coussins,
                traversins=traversins_cfg,
                couleurs=couleurs,
                window_title="Canapé U - 2 Angles",
            )

        fig = plt.gcf()
        # Supprimer tout titre ou supertitre afin d'éviter l'affichage du nom de variante dans les exports
        try:
            fig.suptitle("")
        except Exception:
            pass
        return fig
    except Exception as e:
        plt.close()
        raise Exception(f"Erreur lors de la génération du schéma : {str(e)}")

# Initialiser les variables de session
if 'type_canape' not in st.session_state:
    st.session_state.type_canape = "Simple (S)"
if 'tx' not in st.session_state:
    st.session_state.tx = 280
if 'ty' not in st.session_state:
    st.session_state.ty = 250
if 'tz' not in st.session_state:
    st.session_state.tz = 250
if 'profondeur' not in st.session_state:
    st.session_state.profondeur = 70

# En-tête supprimé
# Les titres initiaux sont retirés pour laisser plus de place au formulaire et à l’aperçu.
st.markdown("", unsafe_allow_html=True)
st.markdown("", unsafe_allow_html=True)

# Création des onglets avec la nouvelle structure :
# 1 : Type, 2 : Dimensions, 3 : Structure (anciennement Options),
# 4 : Coussins, 5 : Mousse (anciennement Matériaux), 6 : Client,
# 7 : Couleurs.
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Type", "Dimensions", "Structure", "Coussins", "Mousse", "Client", "Couleurs"
])

# Onglet 7 : Couleurs
with tab7:
    st.markdown("### Choix des couleurs du schéma")
    st.info(
        "Par défaut, la structure et les banquettes/mousses sont blanches, tandis que les coussins sont beige clair. "
        "Vous pouvez personnaliser ces couleurs ci‑dessous."
    )
    # Sélecteurs de couleur pour la structure (accoudoirs et dossiers)
    color_structure_choice = st.selectbox(
        "Couleur de la structure (accoudoirs et dossiers)",
        list(COLOR_PALETTE.keys()),
        index=list(COLOR_PALETTE.keys()).index("Blanc"),
        key="color_structure_choice",
        help="Choisissez la couleur des accoudoirs et des dossiers, ou laissez Transparent pour ne pas colorier ces éléments."
    )
    # Sélecteur pour la couleur des banquettes/mousses (assise)
    color_banquette_choice = st.selectbox(
        "Couleur des banquettes/mousses (assise)",
        list(COLOR_PALETTE.keys()),
        index=list(COLOR_PALETTE.keys()).index("Blanc"),
        key="color_banquette_choice",
        help="Choisissez la couleur des banquettes/mousses, ou laissez Transparent pour ne pas colorier ces éléments."
    )
    # Sélecteur pour la couleur des coussins
    color_coussins_choice = st.selectbox(
        "Couleur des coussins",
        list(COLOR_PALETTE.keys()),
        index=list(COLOR_PALETTE.keys()).index("Beige clair"),
        key="color_coussins_choice",
        help="Choisissez la couleur des coussins. Le choix par défaut est Beige clair."
    )

# ONGLET 1: TYPE
with tab1:
    st.markdown("### Sélectionnez le type de canapé")
    
    type_canape = st.selectbox(
        "Type de canapé",
        ["Simple (S)", "L - Sans Angle", "L - Avec Angle (LF)", 
         "U - Sans Angle", "U - 1 Angle (U1F)", "U - 2 Angles (U2F)"],
        key="type_canape"
    )

    # Sélecteur pour l'angle de rotation du schéma.
    # En proposant 0°, 90°, 180° et 270°, l'utilisateur peut choisir l'orientation
    # qui lui convient aussi bien pour l'aperçu que pour le PDF.  La valeur est
    # stockée dans la session afin d'être utilisée lors de la génération des schémas.
    rotation_angle = st.selectbox(
        "Rotation du schéma du canapé (PDF / Aperçu)",
        options=[0, 90, 180, 270],
        format_func=lambda x: f"{x}°",
        key="schema_rotation"
    )

# ONGLET 2: DIMENSIONS
with tab2:
    st.markdown("### Dimensions du canapé (en cm)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if "Simple" in st.session_state.type_canape:
            tx = st.number_input("Largeur (Tx)", min_value=100, max_value=600, value=280, step=10, key="tx")
            ty = tz = None
        elif "L" in st.session_state.type_canape:
            tx = st.number_input("Largeur bas (Tx)", min_value=100, max_value=600, value=350, step=10, key="tx")
            ty = st.number_input("Hauteur gauche (Ty)", min_value=100, max_value=600, value=250, step=10, key="ty")
            tz = None
        else:  # U
            tx = st.number_input("Largeur bas (Tx)", min_value=100, max_value=600, value=450, step=10, key="tx")
            ty = st.number_input("Hauteur gauche (Ty)", min_value=100, max_value=600, value=300, step=10, key="ty")
            tz = st.number_input("Hauteur droite (Tz)", min_value=100, max_value=600, value=280, step=10, key="tz")
    
    with col2:
        profondeur = st.number_input("Profondeur d'assise", min_value=50, max_value=120, value=70, step=5, key="profondeur")

# ONGLET 3 : STRUCTURE
with tab3:
    st.markdown("### Composition de la structure")

    # Deux colonnes pour séparer accoudoirs/dossiers et méridienne
    col1, col2 = st.columns(2)

    # Colonne gauche : accoudoirs et dossiers
    with col1:
        st.markdown("**Accoudoirs**")
        # Gestion des accoudoirs selon le type de canapé :
        # Pour les canapés en U (U, U1F, U2F) : uniquement gauche et droite sont visibles et pré-cochés.
        # L'accoudoir bas n'est pas visible et n'est pas pris en compte dans le schéma/prix.
        if "U" in st.session_state.type_canape:
            # Dans le cas des canapés en U : seuls les accoudoirs gauche et droit sont disponibles
            acc_left = st.checkbox("Accoudoir Gauche", value=True)
            acc_right = st.checkbox("Accoudoir Droit", value=True)
            acc_bas = False
            # Mémoriser dans la session les choix des accoudoirs
            st.session_state['acc_left'] = acc_left
            st.session_state['acc_right'] = acc_right
            st.session_state['acc_bas'] = acc_bas
        elif "L" in st.session_state.type_canape:
            # Pour les canapés en L (avec ou sans angle) : on affiche uniquement l'accoudoir gauche et bas
            acc_left = st.checkbox("Accoudoir Gauche", value=True)
            # L'accoudoir droit n'est pas proposé pour les configurations en L
            acc_right = False
            acc_bas = st.checkbox("Accoudoir Bas", value=True)
            # Mémoriser dans la session les choix des accoudoirs
            st.session_state['acc_left'] = acc_left
            st.session_state['acc_right'] = acc_right
            st.session_state['acc_bas'] = acc_bas
        else:
            # Pour les canapés simples : accoudoirs gauche et droit visibles, pas d'accoudoir bas
            acc_left = st.checkbox("Accoudoir Gauche", value=True)
            acc_right = st.checkbox("Accoudoir Droit", value=True)
            acc_bas = False
            # Mémoriser dans la session les choix des accoudoirs
            st.session_state['acc_left'] = acc_left
            st.session_state['acc_right'] = acc_right
            st.session_state['acc_bas'] = acc_bas

        st.markdown("**Dossiers**")
        # Les dossiers sont conservés tels quels : Gauche et Droit visibles selon le type
        dossier_left = st.checkbox("Dossier Gauche", value=True) if "Simple" not in st.session_state.type_canape else False
        dossier_bas = st.checkbox("Dossier Bas", value=True)
        dossier_right = st.checkbox("Dossier Droit", value=True) if ("U" in st.session_state.type_canape) else False
        # Mémoriser dans la session les choix des dossiers
        st.session_state['dossier_left'] = dossier_left
        st.session_state['dossier_bas'] = dossier_bas
        st.session_state['dossier_right'] = dossier_right

    # Colonne droite : méridienne
    with col2:
        st.markdown("**Méridienne**")
        has_meridienne = st.checkbox("Ajouter une méridienne", value=False)

        if has_meridienne:
            # La méridienne peut être placée à gauche, au bas ou à droite.  On stocke
            # directement les codes internes "g", "b" et "d" attendus par le moteur
            # de rendu, tout en affichant des libellés lisibles pour l'utilisateur.
            meridienne_side = st.selectbox(
                "Position de la méridienne",
                ["g", "b", "d"],
                format_func=lambda x: {"g": "Gauche", "b": "Bas", "d": "Droite"}.get(x, x)
            )
            # La longueur de la méridienne est saisie sans limite minimale ni maximale.
            # On laisse un pas de 10 cm pour faciliter la saisie.
            meridienne_len = st.number_input("Longueur (cm)", min_value=0, value=50, step=10)
        else:
            # Pas de méridienne : on stocke None pour le côté et 0 pour la longueur.
            meridienne_side = None
            meridienne_len = 0
        # Mémoriser dans la session les paramètres de la méridienne
        st.session_state['has_meridienne'] = has_meridienne
        st.session_state['meridienne_side'] = meridienne_side
        st.session_state['meridienne_len'] = meridienne_len

        # fin de la colonne méridienne

# ONGLET 4 : COUSSINS
with tab4:
    st.markdown("### Composition des coussins")
    
    # Choix du type de coussins (inchangé)
    type_coussins = st.selectbox(
        "Type de coussins",
        ["auto", "65", "80", "90", "80-90", "valise", "g", "p"],
        help="Auto = optimisation automatique, 80-90 = optimisation par côté entre 80 et 90 cm;\nvalise/p/g = optimisation sur plage de tailles valise (p=petit, g=grand)."
    )

    nb_coussins_deco = st.number_input("Coussins décoratifs", min_value=0, max_value=10, value=0)

    # --- NOUVELLE LOGIQUE TRAVERSINS ---    
    # Déterminer les options selon le type de canapé
    # Si le type contient "L", on propose Gauche/Bas, sinon (Simple/U) Gauche/Droite
    is_L_shape = "L" in st.session_state.type_canape
    
    if is_L_shape:
        # Options pour canapés d'angle (L)
        options_traversins = ["Aucun", "Gauche", "Bas", "Gauche et Bas"]
    else:
        # Options pour Simple et U (selon votre demande : gauche/droite)
        options_traversins = ["Aucun", "Gauche", "Droite", "Gauche et Droite"]
    
    # Sélection unique intuitive
    choix_traversins = st.selectbox(
        "Traversins",
        options_traversins,
        index=0, # "Aucun" par défaut
        key="choix_traversins_ui"
    )

    # Conversion du choix utilisateur en variables techniques pour le moteur de rendu
    traversins_positions = []
    
    if choix_traversins == "Gauche":
        traversins_positions = ["Gauche"]
    elif choix_traversins == "Droite":
        traversins_positions = ["Droite"]
    elif choix_traversins == "Bas":
        traversins_positions = ["Bas"]
    elif choix_traversins == "Gauche et Droite":
        traversins_positions = ["Gauche", "Droite"]
    elif choix_traversins == "Gauche et Bas":
        traversins_positions = ["Gauche", "Bas"]
    # Si "Aucun", la liste reste vide []

    # Calcul automatique des nombres pour le pricing
    nb_traversins_supp = len(traversins_positions)
    nb_traversins_effectif = nb_traversins_supp

    # --- FIN NOUVELLE LOGIQUE ---

    # Option surmatelas (hors du bloc précédent pour toujours proposer la case)
    has_surmatelas = st.checkbox("Surmatelas")

    # Mémoriser dans la session les informations liées aux coussins et traversins
    # Ces variables sont essentielles pour que le PDF et le Pricing fonctionnent
    st.session_state['type_coussins'] = type_coussins
    st.session_state['nb_coussins_deco'] = nb_coussins_deco
    st.session_state['nb_traversins_supp'] = nb_traversins_supp
    st.session_state['traversins_positions'] = traversins_positions
    st.session_state['nb_traversins_effectif'] = nb_traversins_effectif
    st.session_state['has_surmatelas'] = has_surmatelas

# ONGLET 5 : MOUSSE
with tab5:
    st.markdown("### Paramètres de la mousse")
    
    col1, col2 = st.columns(2)
    
    with col1:
        type_mousse = st.selectbox("Type de mousse", ["D25", "D30", "HR35", "HR45"])
        epaisseur = st.number_input("Épaisseur (cm)", min_value=15, max_value=35, value=25, step=5)
        # Ajout de l'option arrondis (par défaut cochée) permettant de majorer le prix de 20€ par banquette et par banquette d'angle
        arrondis = st.checkbox("Arrondis (bords arrondis)", value=True)
        # Mémoriser ces valeurs dans la session pour l'aperçu global
        st.session_state['type_mousse'] = type_mousse
        st.session_state['epaisseur'] = epaisseur
        st.session_state['arrondis'] = arrondis
    
    with col2:
        st.info("Les options de tissus seront affichées après validation de la configuration")

# ONGLET 6 : CLIENT
with tab6:
    st.markdown("### Informations Client")
    st.markdown("Renseignez les coordonnées du client pour finaliser le devis")
    
    col_client1, col_client2 = st.columns(2)
    
    with col_client1:
        # Le nom du client n'est plus obligatoire : on retire l'astérisque et on laisse le champ facultatif
        nom_client = st.text_input("Nom du client", placeholder="Entrez le nom du client")
        telephone_client = st.text_input("N° de téléphone", placeholder="06 12 34 56 78")
    
    with col_client2:
        email_client = st.text_input("Email (optionnel)", placeholder="client@example.com")
        departement_client = st.text_input("Département", placeholder="Ex: Nord (59)")
    
    if email_client:
        st.info("L'email permet d'envoyer le devis au client")

    # -----------------------------------

    # Options pour afficher ou non les pages détaillées du devis et du coût de revient dans le PDF
    show_marge = st.checkbox(
        "Voir la marge",
        value=False,
        help="Lorsque cette option est cochée, la marge HT est affichée dans l'aperçu."
    )
    show_detail_devis = st.checkbox(
        "Afficher le détail du devis (page 2)",
        value=False,
        help="Lorsque cette option est cochée, la page 2 du PDF affichera le tableau complet des calculs du prix."
    )
    show_detail_cr = st.checkbox(
        "Afficher le détail du coût de revient (page 3)",
        value=False,
        help="Lorsque cette option est cochée, la page 3 du PDF affichera le tableau complet des calculs du coût de revient."
    )

    # Option pour afficher le détail du prix usine en page 4
    show_detail_usine = st.checkbox(
        "Afficher le détail du prix usine (page 4)",
        value=False,
        help="Lorsque cette option est cochée, une page supplémentaire est ajoutée pour présenter le tableau complet des prix usine (HT et TTC)."
    )

    # ---------------------------------------------------------------------
    # Note : L'option de rotation du schéma est désormais définie dans l'onglet « Type ».  
    # Le selectbox correspondant y a été déplacé afin d'être directement accessible
    # lorsque l'utilisateur choisit le type de canapé.

    # Stocker les choix dans la session pour les utiliser lors de la génération du PDF
    st.session_state['show_marge'] = show_marge
    st.session_state['show_detail_devis'] = show_detail_devis
    st.session_state['show_detail_cr'] = show_detail_cr
    st.session_state['show_detail_usine'] = show_detail_usine

    st.markdown("### Actions")

    col1, col2 = st.columns(2)

    with col1:
        # L'aperçu est désormais affiché en bas de page pour toutes les catégories.
        st.info("L'aperçu du schéma apparaît en bas de la page et se met à jour automatiquement.")
        # On désactive le code de prévisualisation ici.
        if False:
            with st.spinner("Mise à jour du schéma en cours..."):
                try:
                    # Préparer le dictionnaire de couleurs à partir des choix de l'utilisateur
                    try:
                        struct_choice = st.session_state.get('color_structure_choice')
                    except Exception:
                        struct_choice = None
                    try:
                        banq_choice = st.session_state.get('color_banquette_choice')
                    except Exception:
                        banq_choice = None
                    try:
                        cous_choice = st.session_state.get('color_coussins_choice')
                    except Exception:
                        cous_choice = None
                    # Construire la palette de couleurs pour le schéma.  Si la couleur de la structure
                    # (accoudoirs/dossiers) est "Transparent", on utilise une chaîne vide pour accoudoirs
                    # et dossiers afin d'éviter un éclaircissement par défaut dans canapematplot.
                    struct_val = COLOR_PALETTE.get(struct_choice)
                    if struct_val is None:
                        acc_val = ""
                        dos_val = ""
                    else:
                        acc_val = struct_val
                        dos_val = struct_val
                    ass_val = COLOR_PALETTE.get(banq_choice)
                    ass_val = ass_val if ass_val is not None else None
                    cous_val = COLOR_PALETTE.get(cous_choice)
                    couleurs = {
                        'accoudoirs': acc_val,
                        'dossiers': dos_val,
                        'assise': ass_val,
                        'coussins': cous_val,
                    }

                    # Déterminer l'angle choisi pour la rotation.  Si cet angle
                    # est non nul, on pivote le texte des dimensions dans le schéma
                    # en sens inverse afin qu'il reste lisible après la rotation
                    # globale de l'image.  Pour cela, on remplace temporairement
                    # la méthode _MplTurtle.write de canapematplot de façon à
                    # fournir un paramètre ``rotation`` négatif.
                    rotation_angle = st.session_state.get("schema_rotation", 0)
                    # Sauvegarder l'implémentation originale de write()
                    original_write = canapematplot._MplTurtle.write
                    if rotation_angle not in (0, 360, -360):
                        def rotated_write(self, text, align="left", font=None):
                            ha = {"left": "left", "center": "center", "right": "right"}.get(align, "left")
                            kwargs = {}
                            if font:
                                if len(font) >= 2:
                                    kwargs["fontfamily"] = font[0]
                                    kwargs["fontsize"] = font[1]
                                if len(font) >= 3 and str(font[2]).lower() == "bold":
                                    kwargs["fontweight"] = "bold"
                            # Appliquer une rotation négative de l'angle choisi
                            self.ax.text(self.x, self.y, str(text), ha=ha, va="center",
                                         rotation=-(rotation_angle), **kwargs)
                        canapematplot._MplTurtle.write = rotated_write
                    # Générer le schéma avec les paramètres actuels
                    fig = generer_schema_canape(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx, ty=st.session_state.ty, tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        acc_left=acc_left, acc_right=acc_right, acc_bas=acc_bas,
                        dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                        meridienne_side=meridienne_side, meridienne_len=meridienne_len,
                        coussins=type_coussins,
                        nb_traversins_supp=nb_traversins_supp,
                        traversins_positions=traversins_positions,
                        couleurs=couleurs
                    )
                    # Restaurer la méthode write d'origine si elle a été surchargée
                    if rotation_angle not in (0, 360, -360):
                        canapematplot._MplTurtle.write = original_write

                    # Préparer une fonction utilitaire pour calculer les prix HT
                    base_params = {
                        'type_canape': st.session_state.type_canape,
                        'tx': st.session_state.tx, 'ty': st.session_state.ty, 'tz': st.session_state.tz,
                        'profondeur': st.session_state.profondeur,
                        'type_coussins': type_coussins,
                        'type_mousse': type_mousse, 'epaisseur': epaisseur,
                        'acc_left': acc_left, 'acc_right': acc_right, 'acc_bas': acc_bas,
                        'dossier_left': dossier_left, 'dossier_bas': dossier_bas, 'dossier_right': dossier_right,
                        'nb_coussins_deco': nb_coussins_deco, 'nb_traversins_supp': nb_traversins_effectif,
                        'has_surmatelas': has_surmatelas,
                        'has_meridienne': has_meridienne,
                        # transmettre également les positions des traversins pour un calcul cohérent
                        'traversins_positions': traversins_positions
                    }
                    def price_ht_for(update_dict):
                        params = base_params.copy()
                        params.update(update_dict)
                        return calculer_prix_total(**params)['prix_ht']

                    # Déterminer le nombre de banquettes et d'angles
                    nb_banquettes, nb_angles = 0, 0
                    tc = st.session_state.type_canape
                    if "Simple" in tc:
                        nb_banquettes, nb_angles = 1, 0
                    elif "L - Sans Angle" in tc:
                        nb_banquettes, nb_angles = 2, 0
                    elif "L - Avec Angle" in tc:
                        nb_banquettes, nb_angles = 2, 1
                    elif "U - Sans Angle" in tc:
                        nb_banquettes, nb_angles = 3, 0
                    elif "U - 1 Angle" in tc:
                        nb_banquettes, nb_angles = 3, 1
                    elif "U - 2 Angles" in tc:
                        nb_banquettes, nb_angles = 3, 2

                    # Prix de base (banquettes seules avec mousse de base D25 et sans options)
                    alt_no_extras_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': 'auto', 'nb_coussins_deco': 0, 'nb_traversins_supp': 0, 'has_surmatelas': False,
                        'type_mousse': 'D25'
                    })

                    # Prix avec accoudoirs uniquement (mousse base)
                    alt_with_acc_ht = price_ht_for({
                        'acc_left': acc_left, 'acc_right': acc_right, 'acc_bas': acc_bas,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': 'auto', 'nb_coussins_deco': 0, 'nb_traversins_supp': 0, 'has_surmatelas': False,
                        'type_mousse': 'D25'
                    })
                    price_acc = max(0, alt_with_acc_ht - alt_no_extras_ht)

                    # Prix avec dossiers uniquement (mousse base)
                    alt_with_dossier_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': dossier_left, 'dossier_bas': dossier_bas, 'dossier_right': dossier_right,
                        'type_coussins': 'auto', 'nb_coussins_deco': 0, 'nb_traversins_supp': 0, 'has_surmatelas': False,
                        'type_mousse': 'D25'
                    })
                    price_dossiers = max(0, alt_with_dossier_ht - alt_no_extras_ht)

                    # Prix avec mousse sélectionnée (sans autres options)
                    alt_with_mousse_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': 'auto', 'nb_coussins_deco': 0, 'nb_traversins_supp': 0, 'has_surmatelas': False,
                        'type_mousse': type_mousse
                    })
                    price_mousse = max(0, alt_with_mousse_ht - alt_no_extras_ht)

                    # Prix des coussins (assise + déco + traversins + surmatelas) avec mousse base
                    alt_with_coussins_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': type_coussins, 'nb_coussins_deco': nb_coussins_deco, 'nb_traversins_supp': nb_traversins_supp, 'has_surmatelas': has_surmatelas,
                        'type_mousse': 'D25'
                    })
                    price_coussins_total = max(0, alt_with_coussins_ht - alt_no_extras_ht)

                    # Total hors arrondis (base + options)
                    prix_ht_sans_arrondis = alt_no_extras_ht + price_acc + price_dossiers + price_mousse + price_coussins_total

                    # Calcul complet du devis via le module de pricing (inclut arrondis)
                    prix_details_full = calculer_prix_total(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx, ty=st.session_state.ty, tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        type_coussins=type_coussins, type_mousse=type_mousse, epaisseur=epaisseur,
                        acc_left=acc_left, acc_right=acc_right, acc_bas=acc_bas,
                        dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                        nb_coussins_deco=nb_coussins_deco, nb_traversins_supp=nb_traversins_supp,
                        has_surmatelas=has_surmatelas, has_meridienne=has_meridienne,
                        arrondis=arrondis,
                        traversins_positions=traversins_positions
                    )
                    # Récupération des totaux HT et TTC
                    prix_ht_total = prix_details_full.get('prix_ht', 0.0)
                    prix_ttc_total_avant_remise = prix_details_full.get('total_ttc', 0.0)

                    # Récupération de la remise
                    reduction_ttc = st.session_state.get('reduction_ttc', 0.0) or 0.0
                    reduction_ht = reduction_ttc / 1.20 if reduction_ttc else 0.0

                    prix_ht_apres_remise = max(0, prix_ht_total - reduction_ht)
                    tva_apres_remise = round(prix_ht_apres_remise * 0.20, 2)
                    total_ttc_apres_remise = round(prix_ht_apres_remise + tva_apres_remise, 2)

                    # Montant TTC des arrondis pour l'affichage dans le récapitulatif
                    # On récupère le montant TTC directement depuis le module de pricing
                    suppl_arrondis_ttc = prix_details_full.get('arrondis_total', 0.0)

                    # Quantités
                    nb_acc_selected = int(acc_left) + int(acc_right) + int(acc_bas)
                    nb_dossier_selected = int(dossier_left) + int(dossier_bas) + int(dossier_right)

                    # Nombre de coussins d'assise (approximation si dimension numérique)
                    nb_coussins_assise = 0
                    try:
                        couss_dim = int(type_coussins)
                        bench_lengths = []
                        if "Simple" in tc:
                            bench_lengths = [st.session_state.tx]
                        elif "L" in tc:
                            bench_lengths = [st.session_state.ty, st.session_state.tx]
                        else:
                            bench_lengths = [st.session_state.ty, st.session_state.tx, st.session_state.tz]
                        import math
                        for lng in bench_lengths:
                            nb_coussins_assise += math.ceil(lng / couss_dim)
                    except Exception:
                        nb_coussins_assise = 0

                    nb_arrondis_units = nb_banquettes + nb_angles

                    # Construction détaillée du tableau de synthèse
                    # Prix des coussins par catégorie
                    # Prix des coussins d'assise uniquement (hors déco/traversins/surmatelas)
                    alt_only_assise_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': type_coussins,
                        'nb_coussins_deco': 0, 'nb_traversins_supp': 0, 'has_surmatelas': False,
                        'type_mousse': 'D25'
                    })
                    price_assise = max(0, alt_only_assise_ht - alt_no_extras_ht)

                    # Prix avec coussins déco ajoutés
                    alt_assise_deco_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': type_coussins,
                        'nb_coussins_deco': nb_coussins_deco, 'nb_traversins_supp': 0, 'has_surmatelas': False,
                        'type_mousse': 'D25'
                    })
                    price_decoratif = max(0, alt_assise_deco_ht - alt_only_assise_ht)

                    # Prix avec traversins supplémentaires
                    alt_assise_traversins_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': type_coussins,
                        'nb_coussins_deco': 0, 'nb_traversins_supp': nb_traversins_supp, 'has_surmatelas': False,
                        'type_mousse': 'D25'
                    })
                    price_traversins = max(0, alt_assise_traversins_ht - alt_only_assise_ht)

                    # Prix avec surmatelas
                    alt_assise_surmatelas_ht = price_ht_for({
                        'acc_left': False, 'acc_right': False, 'acc_bas': False,
                        'dossier_left': False, 'dossier_bas': False, 'dossier_right': False,
                        'type_coussins': type_coussins,
                        'nb_coussins_deco': 0, 'nb_traversins_supp': 0, 'has_surmatelas': True,
                        'type_mousse': 'D25'
                    }) if has_surmatelas else alt_only_assise_ht
                    price_surmatelas = max(0, alt_assise_surmatelas_ht - alt_only_assise_ht) if has_surmatelas else 0

                    # Répartition du prix de la mousse par banquette (proportionnelle à la longueur)
                    bench_lengths = []
                    if "Simple" in tc:
                        bench_lengths = [st.session_state.tx]
                    elif "L" in tc:
                        bench_lengths = [st.session_state.ty, st.session_state.tx]
                    else:
                        bench_lengths = [st.session_state.ty, st.session_state.tx, st.session_state.tz]
                    total_length = sum(bench_lengths) if bench_lengths else 1
                    price_mousse_per_bench = []
                    for bl in bench_lengths:
                        part = (price_mousse * bl / total_length) if total_length > 0 else 0
                        price_mousse_per_bench.append(part)

                    breakdown_rows = []
                    # Banquettes de base
                    breakdown_rows.append(("Banquettes", nb_banquettes, f"{alt_no_extras_ht:.2f} €"))
                    # Accoudoirs
                    breakdown_rows.append(("Accoudoirs", nb_acc_selected, f"{price_acc:.2f} €"))
                    # Coussins d'assise
                    breakdown_rows.append(("Coussins assise", nb_coussins_assise, f"{price_assise:.2f} €"))
                    # Coussins décoratifs
                    breakdown_rows.append(("Coussins déco", nb_coussins_deco, f"{price_decoratif:.2f} €"))
                    # Traversins supplémentaires
                    breakdown_rows.append(("Traversins", nb_traversins_supp, f"{price_traversins:.2f} €"))
                    # Surmatelas
                    # Déterminer le nombre de surmatelas en se basant sur le total TTC renvoyé par
                    # ``calculer_prix_total``.  Lorsque l'option surmatelas est activée, la fonction
                    # de pricing ajoute un surmatelas par mousse (dimension) et renvoie un total TTC
                    # égal à 80 € par unité.  On divise donc ce total par 80 pour obtenir la quantité.
                    surmatelas_total_ttc = prix_details_full.get('surmatelas_total', 0.0)
                    nb_surmatelas_units = int(round(surmatelas_total_ttc / 80.0)) if has_surmatelas else 0
                    breakdown_rows.append(("Surmatelas", nb_surmatelas_units, f"{price_surmatelas:.2f} €"))
                    # Dossiers
                    breakdown_rows.append(("Dossiers", nb_dossier_selected, f"{price_dossiers:.2f} €"))
                    # Mousse par banquette
                    for idx, part_price in enumerate(price_mousse_per_bench, start=1):
                        # Libellé de la dimension : on utilise l'indice de la banquette pour différencier
                        breakdown_rows.append((f"Mousse {type_mousse} dim.{idx}", 1, f"{part_price:.2f} €"))
                    # Arrondis
                    # Utiliser le montant TTC récupéré dans prix_details_full pour l'affichage
                    breakdown_rows.append(("Arrondis", nb_arrondis_units, f"{suppl_arrondis_ttc:.2f} €"))
                    # Tissu (inclus)
                    breakdown_rows.append(("Tissu (inclus)", "", "0.00 €"))
                    # Remise
                    if reduction_ttc and reduction_ttc > 0:
                        breakdown_rows.append(("Remise", "", f"-{reduction_ttc:.2f} €"))
                    # Livraison
                    breakdown_rows.append(("Livraison bas d'immeuble/maison", "", "Gratuit"))
                    # Total TTC après remise
                    breakdown_rows.append(("Total TTC", "", f"{total_ttc_apres_remise:.2f} €"))

                    # Calcul du prix TTC total avant remise (conversion du HT en TTC)
                    prix_ttc_total_avant_remise = round(prix_ht_total * 1.20, 2)
                    # On calcule à nouveau le coût de revient pour intégrer correctement les arrondis
                    prix_details_calc = calculer_prix_total(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx, ty=st.session_state.ty, tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        type_coussins=type_coussins, type_mousse=type_mousse, epaisseur=epaisseur,
                        acc_left=acc_left, acc_right=acc_right, acc_bas=acc_bas,
                        dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                        nb_coussins_deco=nb_coussins_deco, nb_traversins_supp=nb_traversins_supp,
                        has_surmatelas=has_surmatelas, has_meridienne=has_meridienne,
                        arrondis=arrondis,
                        traversins_positions=traversins_positions
                    )
                    cout_revient_ht_total = prix_details_calc.get('cout_revient_ht', 0.0)
                    # Marge totale HT = (prix TTC après remise converti en HT) - coût de revient HT
                    marge_totale_ht = round((total_ttc_apres_remise / 1.20) - cout_revient_ht_total, 2)

                    # Affichage du schéma et d'un résumé simplifié du devis
                    st.success("✅ Schéma généré avec succès !")
                    # Convertir la figure en image et appliquer la rotation si nécessaire
                    img_preview = BytesIO()
                    # Augmenter le DPI pour une meilleure netteté de l'aperçu
                    fig.savefig(img_preview, format="png", bbox_inches="tight", dpi=200)
                    img_preview.seek(0)
                    # Récupérer l'angle de rotation choisi (0, 90, 180 ou 270)
                    rotation_angle = st.session_state.get("schema_rotation", 0)
                    # Ouvrir l'image pour appliquer les transformations
                    pil_img = Image.open(img_preview)
                    # Appliquer la rotation si nécessaire
                    if rotation_angle % 360 in (90, 180, 270):
                        pil_img = pil_img.rotate(rotation_angle, expand=True)
                    # Ne pas ajouter de légende externe ; on conserve les dimensions internes qui ont
                    # été pivotées individuellement via le patch de la méthode write.
                    # Convertir l'image finale en buffer pour l'affichage dans Streamlit
                    out_buf = BytesIO()
                    pil_img.save(out_buf, format="PNG")
                    out_buf.seek(0)
                    # Afficher l'image dans l'application
                    # Afficher l'image et les informations de prix/marge dans une disposition en colonnes
                    # Créer trois colonnes : une colonne pour les prix/marge, une pour le schéma, et une pour laisser de l'espace
                    price_col, schema_col, empty_col = st.columns([2, 5, 1])
                    with price_col:
                        # Récupérer la réduction TTC depuis la session pour l'afficher (elle peut avoir été modifiée via l'aperçu)
                        current_reduc = float(st.session_state.get('reduction_ttc', 0.0) or 0.0)
                        # Affichage du prix TTC, de la marge totale HT et de la réduction TTC appliquée
                        st.markdown(f"**Prix TTC :** {total_ttc_apres_remise:.2f} €")
                        if st.session_state.get('show_marge', False):
                            st.markdown(f"**Marge HT :** {marge_totale_ht:.2f} €")
                        # Affichage de la réduction TTC saisie, en négatif pour rappel
                        st.markdown(f"**Réduction TTC :** -{current_reduc:.2f} €")
                    with schema_col:
                        # Afficher l'image à sa largeur réelle pour éviter les déformations
                        st.image(out_buf, width=pil_img.width)
                    # Fermer la figure matplotlib pour libérer la mémoire
                    plt.close(fig)
                    # Résumé texte en dessous de l'image et des prix
                    st.markdown("### 🧾 Résumé du devis", unsafe_allow_html=True)
                    st.markdown(f"**Prix de vente TTC total avant réduction :** {prix_ttc_total_avant_remise:.2f} €")
                    if reduction_ttc and reduction_ttc > 0:
                        st.markdown(f"**Réduction TTC :** -{reduction_ttc:.2f} €")
                    st.markdown(f"**Prix de vente TTC total après réduction :** {total_ttc_apres_remise:.2f} €")
                    if st.session_state.get('show_marge', False):
                        st.markdown(f"**Marge totale HT :** {marge_totale_ht:.2f} €")

                    # Stockage des valeurs pour utilisation lors de la génération du PDF
                    st.session_state['breakdown_rows'] = breakdown_rows
                    st.session_state['prix_ht'] = prix_ht_apres_remise
                    st.session_state['tva'] = tva_apres_remise
                    st.session_state['total_ttc'] = total_ttc_apres_remise
                    st.session_state['remise_ttc'] = reduction_ttc

                except Exception as e:
                    st.error(f"❌ Erreur : {str(e)}")

    with col2:
        # Bouton pour générer un devis PDF
        if st.button("📄 Générer le Devis PDF", type="primary", use_container_width=True, key="btn_gen_pdf"):
            with st.spinner("Création du devis PDF en cours..."):
                try:
                    # Récupérer les couleurs choisies et construire la palette pour le schéma
                    struct_choice = st.session_state.get('color_structure_choice')
                    banq_choice = st.session_state.get('color_banquette_choice')
                    cous_choice = st.session_state.get('color_coussins_choice')
                    struct_val = COLOR_PALETTE.get(struct_choice)
                    if struct_val is None:
                        acc_val = ""
                        dos_val = ""
                    else:
                        acc_val = struct_val
                        dos_val = struct_val
                    ass_val = COLOR_PALETTE.get(banq_choice)
                    ass_val = ass_val if ass_val is not None else None
                    cous_val = COLOR_PALETTE.get(cous_choice)
                    couleurs = {
                        "accoudoirs": acc_val,
                        "dossiers": dos_val,
                        "assise": ass_val,
                        "coussins": cous_val,
                    }
                    # Angle de rotation
                    rotation_angle = st.session_state.get("schema_rotation", 0)
                    original_write = canapematplot._MplTurtle.write
                    if rotation_angle not in (0, 360, -360):
                        def rotated_write(self, text, align="left", font=None):
                            ha = {"left": "left", "center": "center", "right": "right"}.get(align, "left")
                            kwargs = {}
                            if font:
                                if len(font) >= 2:
                                    kwargs["fontfamily"] = font[0]
                                    kwargs["fontsize"] = font[1]
                                if len(font) >= 3 and str(font[2]).lower() == "bold":
                                    kwargs["fontweight"] = "bold"
                            self.ax.text(
                                self.x,
                                self.y,
                                str(text),
                                ha=ha,
                                va="center",
                                rotation=-(rotation_angle),
                                **kwargs,
                            )
                        canapematplot._MplTurtle.write = rotated_write
                    # Générer le schéma du canapé
                    fig = generer_schema_canape(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx,
                        ty=st.session_state.ty,
                        tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        acc_left=st.session_state.get('acc_left', False),
                        acc_right=st.session_state.get('acc_right', False),
                        acc_bas=st.session_state.get('acc_bas', False),
                        dossier_left=st.session_state.get('dossier_left', False),
                        dossier_bas=st.session_state.get('dossier_bas', False),
                        dossier_right=st.session_state.get('dossier_right', False),
                        meridienne_side=st.session_state.get('meridienne_side'),
                        meridienne_len=st.session_state.get('meridienne_len', 0),
                        coussins=st.session_state.get('type_coussins', 'auto'),
                        nb_traversins_supp=st.session_state.get('nb_traversins_effectif', 0),
                        traversins_positions=st.session_state.get('traversins_positions', []),
                        couleurs=couleurs,
                    )
                    if rotation_angle not in (0, 360, -360):
                        canapematplot._MplTurtle.write = original_write
                    # Sauvegarder le schéma en mémoire
                    tmp_buffer = BytesIO()
                    fig.savefig(tmp_buffer, format="png", bbox_inches="tight", dpi=200)
                    tmp_buffer.seek(0)
                    plt.close(fig)
                    pil_img = Image.open(tmp_buffer)
                    # Rotation de l'image si nécessaire
                    if rotation_angle % 360 in (90, 180, 270):
                        pil_img = pil_img.rotate(rotation_angle, expand=True)
                    img_buffer = BytesIO()
                    pil_img.save(img_buffer, format="PNG")
                    img_buffer.seek(0)
                    # Préparer la configuration et recalculer le prix
                    config = {
                        "type_canape": st.session_state.type_canape,
                        "dimensions": {
                            "tx": st.session_state.tx,
                            "ty": st.session_state.ty,
                            "tz": st.session_state.tz,
                            "profondeur": st.session_state.profondeur,
                        },
                        "options": {
                            "acc_left": st.session_state.get('acc_left', False),
                            "acc_right": st.session_state.get('acc_right', False),
                            "acc_bas": st.session_state.get('acc_bas', False),
                            "dossier_left": st.session_state.get('dossier_left', False),
                            "dossier_bas": st.session_state.get('dossier_bas', False),
                            "dossier_right": st.session_state.get('dossier_right', False),
                            "meridienne_side": st.session_state.get('meridienne_side'),
                            "meridienne_len": st.session_state.get('meridienne_len', 0),
                            "type_coussins": st.session_state.get('type_coussins', 'auto'),
                            "type_mousse": st.session_state.get('type_mousse', 'D25'),
                            "epaisseur": st.session_state.get('epaisseur', 25),
                            "arrondis": st.session_state.get('arrondis', True),
                        },
                        "client": {
                            "nom": st.session_state.get('nom_client', nom_client),
                            "email": st.session_state.get('email_client', email_client),
                            "telephone": st.session_state.get('telephone_client', telephone_client),
                            "departement": st.session_state.get('departement_client', departement_client),
                        },
                    }
                    # Calcul du prix
                    prix_details = calculer_prix_total(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx,
                        ty=st.session_state.ty,
                        tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        type_coussins=st.session_state.get('type_coussins', 'auto'),
                        type_mousse=st.session_state.get('type_mousse', 'D25'),
                        epaisseur=st.session_state.get('epaisseur', 25),
                        acc_left=st.session_state.get('acc_left', False),
                        acc_right=st.session_state.get('acc_right', False),
                        acc_bas=st.session_state.get('acc_bas', False),
                        dossier_left=st.session_state.get('dossier_left', False),
                        dossier_bas=st.session_state.get('dossier_bas', False),
                        dossier_right=st.session_state.get('dossier_right', False),
                        nb_coussins_deco=st.session_state.get('nb_coussins_deco', 0),
                        nb_traversins_supp=st.session_state.get('nb_traversins_effectif', 0),
                        has_surmatelas=st.session_state.get('has_surmatelas', False),
                        has_meridienne=st.session_state.get('has_meridienne', False),
                        arrondis=st.session_state.get('arrondis', True),
                        traversins_positions=st.session_state.get('traversins_positions', []),
                        surplus=st.session_state.get('surplus_ttc', 0.0) # <--- AJOUT ICI
                    )
                    # Appliquer la réduction TTC si nécessaire
                    reduction_ttc = st.session_state.get('reduction_ttc', 0.0) or 0.0
                    if reduction_ttc > 0:
                        reduction_ht = reduction_ttc / 1.20
                        prix_details['prix_ht'] = max(0, prix_details['prix_ht'] - reduction_ht)
                        prix_details['tva'] = round(prix_details['prix_ht'] * 0.20, 2)
                        prix_details['total_ttc'] = round(prix_details['prix_ht'] + prix_details['tva'], 2)
                        prix_details['reduction_ttc'] = reduction_ttc
                    else:
                        prix_details['reduction_ttc'] = 0.0
                    breakdown_rows = st.session_state.get('breakdown_rows', None)
                    nom_fichier_base = f"devis_canape_{(nom_client or 'client').replace(' ', '_')}"
                    pdf_buffer = generer_pdf_devis(
                        config,
                        prix_details,
                        schema_image=img_buffer,
                        breakdown_rows=breakdown_rows,
                        reduction_ttc=prix_details.get('reduction_ttc', 0.0),
                        show_detail_devis=st.session_state.get('show_detail_devis', False),
                        show_detail_cr=st.session_state.get('show_detail_cr', False),
                        show_detail_usine=st.session_state.get('show_detail_usine', False),
                    )
                    st.download_button(
                        label="⬇️ Télécharger le Devis PDF",
                        data=pdf_buffer,
                        file_name=f"{nom_fichier_base}.pdf",
                        mime="application/pdf",
                        key="download_devis_pdf",
                    )
                    st.success("✅ Devis PDF généré avec succès !")
                except Exception as e:
                    st.error(f"❌ Erreur : {str(e)}")
# Bouton pour générer un devis PNG
        if st.button("🖼️ Générer le Devis PNG", type="secondary", use_container_width=True, key="btn_gen_png"):
            with st.spinner("Création du devis PNG en cours..."):
                try:
                    # 1. Génération du schéma (Copie conforme du bloc PDF)
                    struct_choice = st.session_state.get('color_structure_choice')
                    banq_choice = st.session_state.get('color_banquette_choice')
                    cous_choice = st.session_state.get('color_coussins_choice')
                    
                    couleurs = {
                        "accoudoirs": COLOR_PALETTE.get(struct_choice, "") or "",
                        "dossiers": COLOR_PALETTE.get(struct_choice, "") or "",
                        "assise": COLOR_PALETTE.get(banq_choice, None),
                        "coussins": COLOR_PALETTE.get(cous_choice, None),
                    }
                    
                    # Gestion rotation
                    rotation_angle = st.session_state.get("schema_rotation", 0)
                    original_write = canapematplot._MplTurtle.write
                    if rotation_angle not in (0, 360, -360):
                        # ... (Logique de patch turtle identique au bloc PDF) ...
                        def rotated_write(self, text, align="left", font=None):
                            ha = {"left": "left", "center": "center", "right": "right"}.get(align, "left")
                            kwargs = {}
                            if font:
                                if len(font) >= 2: kwargs["fontfamily"] = font[0]; kwargs["fontsize"] = font[1]
                                if len(font) >= 3 and str(font[2]).lower() == "bold": kwargs["fontweight"] = "bold"
                            self.ax.text(self.x, self.y, str(text), ha=ha, va="center", rotation=-(rotation_angle), **kwargs)
                        canapematplot._MplTurtle.write = rotated_write

                    fig = generer_schema_canape(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx, ty=st.session_state.ty, tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        acc_left=st.session_state.get('acc_left', False),
                        acc_right=st.session_state.get('acc_right', False),
                        acc_bas=st.session_state.get('acc_bas', False),
                        dossier_left=st.session_state.get('dossier_left', False),
                        dossier_bas=st.session_state.get('dossier_bas', False),
                        dossier_right=st.session_state.get('dossier_right', False),
                        meridienne_side=st.session_state.get('meridienne_side'),
                        meridienne_len=st.session_state.get('meridienne_len', 0),
                        coussins=st.session_state.get('type_coussins', 'auto'),
                        nb_traversins_supp=st.session_state.get('nb_traversins_effectif', 0),
                        traversins_positions=st.session_state.get('traversins_positions', []),
                        couleurs=couleurs,
                    )
                    
                    if rotation_angle not in (0, 360, -360):
                        canapematplot._MplTurtle.write = original_write

                    tmp_buffer = BytesIO()
                    fig.savefig(tmp_buffer, format="png", bbox_inches="tight", dpi=200)
                    tmp_buffer.seek(0)
                    plt.close(fig)
                    
                    pil_img = Image.open(tmp_buffer)
                    if rotation_angle % 360 in (90, 180, 270):
                        pil_img = pil_img.rotate(rotation_angle, expand=True)

                    # 2. Calcul des prix (Identique bloc PDF)
                    prix_details = calculer_prix_total(
                        type_canape=st.session_state.type_canape,
                        tx=st.session_state.tx, ty=st.session_state.ty, tz=st.session_state.tz,
                        profondeur=st.session_state.profondeur,
                        type_coussins=st.session_state.get('type_coussins', 'auto'),
                        type_mousse=st.session_state.get('type_mousse', 'D25'),
                        epaisseur=st.session_state.get('epaisseur', 25),
                        acc_left=st.session_state.get('acc_left', False),
                        acc_right=st.session_state.get('acc_right', False),
                        acc_bas=st.session_state.get('acc_bas', False),
                        dossier_left=st.session_state.get('dossier_left', False),
                        dossier_bas=st.session_state.get('dossier_bas', False),
                        dossier_right=st.session_state.get('dossier_right', False),
                        nb_coussins_deco=st.session_state.get('nb_coussins_deco', 0),
                        nb_traversins_supp=st.session_state.get('nb_traversins_effectif', 0),
                        has_surmatelas=st.session_state.get('has_surmatelas', False),
                        has_meridienne=st.session_state.get('has_meridienne', False),
                        arrondis=st.session_state.get('arrondis', True),
                        traversins_positions=st.session_state.get('traversins_positions', []),
                        surplus=st.session_state.get('surplus_ttc', 0.0) # <--- AJOUT ICI
                    )
                    
                    reduction_ttc = st.session_state.get('reduction_ttc', 0.0) or 0.0
                    if reduction_ttc > 0:
                        reduction_ht = reduction_ttc / 1.20
                        prix_details['prix_ht'] = max(0, prix_details['prix_ht'] - reduction_ht)
                        prix_details['tva'] = round(prix_details['prix_ht'] * 0.20, 2)
                        prix_details['total_ttc'] = round(prix_details['prix_ht'] + prix_details['tva'], 2)
                        prix_details['reduction_ttc'] = reduction_ttc

                    # 3. Appel du nouveau générateur PNG
                    # On recrée la config dict comme attendu
                    config_png = {
                        "type_canape": st.session_state.type_canape,
                        "dimensions": {
                            "tx": st.session_state.tx, "ty": st.session_state.ty, "tz": st.session_state.tz,
                            "profondeur": st.session_state.profondeur,
                        },
                        "options": {
                            "type_mousse": st.session_state.get('type_mousse', 'D25'),
                            "epaisseur": st.session_state.get('epaisseur', 25),
                            "type_coussins": st.session_state.get('type_coussins', 'auto'),
                            "acc_left": st.session_state.get('acc_left'),
                            "acc_right": st.session_state.get('acc_right'),
                            "acc_bas": st.session_state.get('acc_bas'),
                            "dossier_left": st.session_state.get('dossier_left'),
                            "dossier_bas": st.session_state.get('dossier_bas'),
                            "dossier_right": st.session_state.get('dossier_right'),
                        },
                        "client": {
                            "nom": nom_client,
                            "telephone": telephone_client,
                        },
                    }
                    
                    # Récupérer les lignes de détail (stockées en session lors de la prévisualisation)
                    breakdown_rows = st.session_state.get('breakdown_rows', None)

                    png_buffer = generer_png_devis(
                        config=config_png,
                        prix_details=prix_details,
                        schema_image=pil_img,
                        breakdown_rows=breakdown_rows,
                        reduction_ttc=reduction_ttc
                    )
                    
                    nom_fichier_base = f"devis_canape_{(nom_client or 'client').replace(' ', '_')}"
                    st.download_button(
                        label="⬇️ Télécharger le Devis PNG",
                        data=png_buffer,
                        file_name=f"{nom_fichier_base}.png",
                        mime="image/png",
                        key="download_devis_png",
                    )
                    st.success("✅ Devis PNG généré avec succès (Mise en page identique PDF) !")
                except Exception as e:
                    st.error(f"❌ Erreur : {str(e)}")
                    # Pour le debug
                    import traceback
                    st.text(traceback.format_exc())
                    
# Footer
# La signature du configurateur est supprimée pour libérer de l’espace.
st.markdown("", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Aperçu global du schéma en bas de page
#
# Afin que l'aperçu du canapé soit visible dans tous les onglets, nous plaçons
# ci‑dessous un bloc qui génère et affiche le schéma à partir des paramètres
# saisis dans les ongets précédents.  Ce bloc est exécuté à chaque
# rafraîchissement de l'application et se met donc à jour automatiquement
# lorsque l'utilisateur modifie le formulaire.

# Titre de l’aperçu supprimé pour optimiser l’espace

# Créer un conteneur pour l'aperçu afin qu'il soit visible sous tous les onglets.
with st.spinner("Mise à jour du schéma en cours..."):
    try:
        # Construire la palette de couleurs en fonction des choix effectués dans l'onglet Couleurs.
        struct_choice = st.session_state.get('color_structure_choice')
        banq_choice = st.session_state.get('color_banquette_choice')
        cous_choice = st.session_state.get('color_coussins_choice')
        struct_val = COLOR_PALETTE.get(struct_choice)
        if struct_val is None:
            acc_val = ""
            dos_val = ""
        else:
            acc_val = struct_val
            dos_val = struct_val
        ass_val = COLOR_PALETTE.get(banq_choice)
        ass_val = ass_val if ass_val is not None else None
        cous_val = COLOR_PALETTE.get(cous_choice)
        couleurs_preview = {
            'accoudoirs': acc_val,
            'dossiers': dos_val,
            'assise': ass_val,
            'coussins': cous_val,
        }

        # Récupérer depuis la session toutes les options nécessaires au dessin du schéma.
        # En cas d'absence de clé (par exemple si l'utilisateur n'a pas encore visité l'onglet),
        # on fournit une valeur par défaut raisonnable.
        tc = st.session_state.get('type_canape', 'Simple (S)')
        tx = st.session_state.get('tx', None)
        ty = st.session_state.get('ty', None)
        tz = st.session_state.get('tz', None)
        profondeur = st.session_state.get('profondeur', 70)

        acc_left_val = st.session_state.get('acc_left', True)
        acc_right_val = st.session_state.get('acc_right', True)
        acc_bas_val = st.session_state.get('acc_bas', False)
        dossier_left_val = st.session_state.get('dossier_left', False)
        dossier_bas_val = st.session_state.get('dossier_bas', True)
        dossier_right_val = st.session_state.get('dossier_right', False)
        has_meridienne_val = st.session_state.get('has_meridienne', False)
        # Si aucune méridienne n'a été définie, ne pas imposer de valeur par défaut
        meridienne_side_val = st.session_state.get('meridienne_side', None)
        meridienne_len_val = st.session_state.get('meridienne_len', 0)

        type_coussins_val = st.session_state.get('type_coussins', 'auto')
        nb_traversins_supp_val = st.session_state.get('nb_traversins_supp', 0)
        traversins_positions_val = st.session_state.get('traversins_positions', [])

        # Angle de rotation choisi par l'utilisateur
        rotation_angle_preview = st.session_state.get('schema_rotation', 0)

        # Patcher temporairement la méthode write de canapematplot pour faire pivoter
        # les annotations internes en sens inverse de l'angle global, uniquement si
        # l'angle n'est pas nul.  Ainsi, les textes restent horizontaux après
        # rotation globale de l'image.
        original_write_preview = canapematplot._MplTurtle.write
        if rotation_angle_preview not in (0, 360, -360):
            def rotated_write_preview(self, text, align="left", font=None):
                ha = {"left": "left", "center": "center", "right": "right"}.get(align, "left")
                kwargs = {}
                if font:
                    if len(font) >= 2:
                        kwargs["fontfamily"] = font[0]
                        kwargs["fontsize"] = font[1]
                    if len(font) >= 3 and str(font[2]).lower() == "bold":
                        kwargs["fontweight"] = "bold"
                self.ax.text(self.x, self.y, str(text), ha=ha, va="center", rotation=-(rotation_angle_preview), **kwargs)
            canapematplot._MplTurtle.write = rotated_write_preview

        # Générer le schéma à l'aide des paramètres récupérés
        fig_preview = generer_schema_canape(
            type_canape=tc,
            tx=tx,
            ty=ty,
            tz=tz,
            profondeur=profondeur,
            acc_left=acc_left_val,
            acc_right=acc_right_val,
            acc_bas=acc_bas_val,
            dossier_left=dossier_left_val,
            dossier_bas=dossier_bas_val,
            dossier_right=dossier_right_val,
            meridienne_side=meridienne_side_val,
            meridienne_len=meridienne_len_val,
            coussins=type_coussins_val,
            nb_traversins_supp=nb_traversins_supp_val,
            traversins_positions=traversins_positions_val,
            couleurs=couleurs_preview
        )

        # Restaurer la méthode originale afin de ne pas impacter d'autres tracés
        if rotation_angle_preview not in (0, 360, -360):
            canapematplot._MplTurtle.write = original_write_preview

        # Convertir la figure en image et appliquer la rotation globale
        preview_buffer = BytesIO()
        # Augmenter le DPI pour l'aperçu global afin d'améliorer la définition sans trop alourdir le temps de calcul
        fig_preview.savefig(preview_buffer, format="png", bbox_inches="tight", dpi=200)
        preview_buffer.seek(0)
        plt.close(fig_preview)
        pil_preview = Image.open(preview_buffer)
        # Si l'angle est non nul, on applique la rotation à l'image entière
        if rotation_angle_preview % 360 in (90, 180, 270):
            pil_preview = pil_preview.rotate(rotation_angle_preview, expand=True)

        # Réduire la taille du schéma.  Après feedback utilisateur, nous diminuons
        # davantage la taille pour qu'elle soit environ 30 % plus petite que
        # la version précédente.  En partant d'un ratio de 0.5, nous appliquons
        # à nouveau une réduction de 30 %, soit un ratio final de 0.35.
        ratio_resize = 0.35
        try:
            new_size = (int(pil_preview.width * ratio_resize), int(pil_preview.height * ratio_resize))
            pil_preview = pil_preview.resize(new_size)
        except Exception:
            pass  # En cas d'échec du redimensionnement, on garde la taille originale

        # Calculer le prix TTC et la marge HT pour l'aperçu afin de les afficher à gauche du schéma
        try:
            prix_details_preview = calculer_prix_total(
                type_canape=tc,
                tx=tx, ty=ty, tz=tz,
                profondeur=profondeur,
                type_coussins=type_coussins_val,
                type_mousse=st.session_state.get('type_mousse', 'HR35'),
                epaisseur=st.session_state.get('epaisseur', 25),
                acc_left=acc_left_val, acc_right=acc_right_val, acc_bas=acc_bas_val,
                dossier_left=dossier_left_val, dossier_bas=dossier_bas_val, dossier_right=dossier_right_val,
                nb_coussins_deco=st.session_state.get('nb_coussins_deco', 0),
                nb_traversins_supp=nb_traversins_supp_val,
                has_surmatelas=st.session_state.get('has_surmatelas', False),
                has_meridienne=has_meridienne_val,
                arrondis=st.session_state.get('arrondis', False),
                traversins_positions=traversins_positions_val,
                departement_livraison=st.session_state.get('departement_client') or None,
                surplus=st.session_state.get('surplus_ttc', 0.0) # <--- AJOUT ICI
            )
            total_ttc_preview = prix_details_preview.get('total_ttc', 0.0)
            marge_ht_preview = prix_details_preview.get('marge_ht', 0.0)
        except Exception:
            total_ttc_preview = 0.0
            marge_ht_preview = 0.0

        # Créer trois colonnes pour centrer l'image
        left_space, img_col, right_space = st.columns([2, 5, 2])
        
        # --- DÉBUT DU BLOC À REMPLACER ---
        with left_space:
            st.markdown("### 💰 Tarification")
            
            # 1. Champ Réduction
            # CORRECTION : On utilise directement key="reduction_ttc"
            # Cela met à jour la session AVANT le calcul du prix en haut du script
            reduc_val = st.number_input(
                "Réduction TTC (€)",
                min_value=0.0,
                value=float(st.session_state.get('reduction_ttc', 0.0)),
                step=10.0,
                help="Saisissez une réduction en euros TTC.",
                key="reduction_ttc" 
            )

            # 2. Champ Surplus
            # CORRECTION : On utilise directement key="surplus_ttc"
            # Cela supprime le décalage (lag) dans le calcul
            surplus_val = st.number_input(
                "Surplus TTC (€)",
                min_value=0.0,
                value=float(st.session_state.get('surplus_ttc', 0.0)),
                step=10.0,
                help="Saisissez un surplus en euros TTC (frais annexes, urgence...).",
                key="surplus_ttc"
            )

            st.divider()

            # 3. Affichage des résultats
            # total_ttc_preview inclut DÉJÀ le surplus car le calcul a été fait plus haut 
            # avec la nouvelle valeur de st.session_state['surplus_ttc'] (grâce au key correct).
            
            # Prix final = Total (inclus surplus) - Réduction
            prix_ttc_final = max(0.0, total_ttc_preview - reduc_val)
            
            # Marge finale = Marge (inclut surplus) - (Coût HT de la réduction)
            # On divise la réduction par 1.20 pour retirer la TVA (approximation standard)
            marge_ht_final = max(0.0, marge_ht_preview - (reduc_val / 1.20))

            st.markdown(f"**Prix TTC :** <span style='color:#28a745; font-size:1.2em'>{prix_ttc_final:.2f} €</span>", unsafe_allow_html=True)
            if st.session_state.get('show_marge', False):
                st.markdown(f"**Marge HT :** {marge_ht_final:.2f} €")
            
        # --- FIN DU BLOC À REMPLACER ---
        
        with img_col:
            # Utiliser la largeur réelle de l'image pour le paramètre `width` garantit qu'elle ne sera pas étirée.
            st.image(pil_preview, width=pil_preview.width)

    except Exception as e:
        st.error(f"❌ Erreur lors de la génération de l'aperçu : {str(e)}")
