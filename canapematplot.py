


def _format_valise_counts_console(
    sizes, counts, total, order=("gauche", "bas", "droite")
):
    """
    Affichage console *valise* : agrège les quantités par dimension et trie selon
    l'ordre des côtés spécifié (défaut: gauche, bas, droite).
    Exemple : "4x86 / 3x83 / 3x81 - total 10".

    Paramètres :
      sizes  : dict {"bas":int,"gauche":int,"droite":int (optionnel)}
      counts : dict même clés -> quantités posées par côté.
      total  : nombre total de coussins posés.
      order  : ordre de priorité des côtés pour le tri (tuple/list).
    """
    from collections import defaultdict

    # Dans certains cas, best["counts"] peut ne pas exister ; counts peut être None.
    if counts is None:
        counts = {}

    # 1) Agrégation par dimension : somme des coussins pour chaque taille.
    agg = defaultdict(int)
    for side, size in sizes.items():
        c = counts.get(side, 0)
        if c > 0:
            agg[size] += c

    # Si aucun coussin, on affiche juste le total.
    if not agg:
        return f"- total {total}"

    # 2) Déterminer pour chaque dimension le premier côté qui l'utilise,
    #    selon l'ordre de priorité indiqué. Ce côté servira à trier les tailles.
    side_index = {side: i for i, side in enumerate(order)}
    first_side_for_size = {}
    for side in order:
        size = sizes.get(side)
        if size is None:
            continue
        if counts.get(side, 0) > 0 and size not in first_side_for_size:
            first_side_for_size[size] = side_index.get(side, len(order))

    # 3) Tri des couples (taille, quantité) :
    #    d'abord par index de côté prioritaire, puis par taille décroissante.
    def sort_key(item):
        size, _ = item
        return (first_side_for_size.get(size, len(order)), -size)

    parts = [
        f"{n}x{sz}"
        for sz, n in sorted(agg.items(), key=sort_key)
    ]
    return " / ".join(parts) + f" - total {total}"

# -------------------------------------------------------------------------
# Comptage pondéré des dossiers
# -------------------------------------------------------------------------

def _compute_dossiers_count(polys):
    """
    Calcule un nombre pondéré de dossiers en appliquant les mêmes heuristiques
    que celles utilisées pour l'affichage détaillé des dossiers.

    Chaque dossier compte pour 1 si sa longueur (corrigée) dépasse 110 cm,
    et pour 0,5 sinon. Les longueurs des dossiers sont déterminées en
    prenant en compte les formes en « L » et les tronçons multiples, afin
    d'aligner le calcul avec celui affiché dans le détail des dossiers.

    Parameters:
        polys (dict): dictionnaire contenant notamment la clé 'dossiers'
                      avec une liste de polygones représentant les dossiers.
    Returns:
        float: le nombre total pondéré de dossiers.
    """
    dossiers = polys.get("dossiers") or []
    # Estimer la profondeur des banquettes (prof) à partir des petites
    # dimensions des banquettes. Cette profondeur est constante pour le canapé.
    prof_candidates = []
    for bp in polys.get("banquettes", []):
        xs_b = [pt[0] for pt in bp]
        ys_b = [pt[1] for pt in bp]
        w_b = max(xs_b) - min(xs_b)
        h_b = max(ys_b) - min(ys_b)
        prof_candidates.append(min(w_b, h_b))
    prof = max(prof_candidates) if prof_candidates else 0

    # Estimer l'épaisseur commune des dossiers (thk) à partir de leurs
    # petites dimensions. Cette valeur vaut typiquement 10 cm lorsqu'un
    # dossier est présent.
    thk_candidates = []
    for dp in dossiers:
        xs_d = [pt[0] for pt in dp]
        ys_d = [pt[1] for pt in dp]
        w_d = max(xs_d) - min(xs_d)
        h_d = max(ys_d) - min(ys_d)
        m = min(w_d, h_d)
        if m > 0:
            thk_candidates.append(m)
    thk = min(thk_candidates) if thk_candidates else 0

    # Déterminer la variante et la présence d'un dossier bas
    variant = polys.get("__variant")
    dossier_bas_present = bool(polys.get("__dossier_bas", False))

    # Préparer des métriques pour chaque dossier : largeur, hauteur, centre et orientation
    widths = []
    heights = []
    cx_list = []
    cy_list = []
    orientations = []
    for dp in dossiers:
        xs_d = [pt[0] for pt in dp]
        ys_d = [pt[1] for pt in dp]
        w_d = max(xs_d) - min(xs_d)
        h_d = max(ys_d) - min(ys_d)
        widths.append(w_d)
        heights.append(h_d)
        cx_list.append(sum(xs_d) / float(len(xs_d)))
        cy_list.append(sum(ys_d) / float(len(ys_d)))
        orientations.append('horiz' if w_d > h_d else 'vert')

    # Identifier les indices des dossiers à ignorer.  On récupère les côtés
    # associés à chaque polygone pour filtrer selon l'activation des dos.
    dossier_left_present = bool(polys.get("__dossier_left", True))
    dossier_bas_present = bool(polys.get("__dossier_bas", False))
    dossier_right_present = bool(polys.get("__dossier_right", True))
    dossier_sides = polys.get("dossiers_sides")
    skip_indices = set()
    if dossier_sides:
        for i, side in enumerate(dossier_sides):
            if side == "left" and not dossier_left_present:
                skip_indices.add(i)
            elif side == "right" and not dossier_right_present:
                skip_indices.add(i)
            elif side == "bottom" and not dossier_bas_present:
                skip_indices.add(i)
    # Supprimer également les pièces horizontales résiduelles lorsque le dossier bas est absent.
    # Ces pièces ont une hauteur très faible (≤ épaisseur) et ne représentent pas un vrai dossier.
    if not dossier_bas_present:
        for i, orient in enumerate(orientations):
            if orient == 'horiz' and i not in skip_indices:
                if thk and heights[i] <= thk + 1e-6:
                    skip_indices.add(i)

    # Position médiane en x pour séparer gauche/droite
    xs_all = []
    for bp in polys.get("banquettes", []):
        for (x, _) in bp:
            xs_all.append(x)
    mid_x = (min(xs_all) + max(xs_all)) / 2.0 if xs_all else 0.0

    # Compter les dossiers horizontaux dont la largeur est égale à la profondeur
    count_prof_horiz = 0
    for idx, (w_d, h_d) in enumerate(zip(widths, heights)):
        if idx in skip_indices:
            continue
        if w_d > h_d and abs(w_d - prof) < 1e-6:
            count_prof_horiz += 1

    # Détecter les dossiers « bridging » selon la variante
    bridging_vert_indices = set()
    bridging_horiz = {}
    # Détection des dossiers verticaux à ajuster pour v1 et v4.  Un dossier
    # vertical « bridging » relie le bas et le côté droit/gauche et doit
    # être réduit à une longueur de ``prof + thk``.  La logique est la
    # suivante : sur le côté droit, on choisit parmi les dossiers
    # verticaux ayant un centre x supérieur à mid_x et une hauteur
    # dépassant 2× la profondeur.  Si l'un de ces candidats dépasse
    # 3× la profondeur, on sélectionne celui ayant la hauteur
    # maximale (c'est le cas des très grands dossiers en L).  Sinon,
    # on sélectionne celui dont le centre y est le plus bas (le plus
    # proche du bas).  Dans la variante v4, on peut également avoir
    # un vertical « bridging » sur le côté gauche si ce dernier est
    # significativement plus haut que l'autre côté ; pour cela, on
    # choisit ce dossier uniquement s'il n'y a qu'un seul candidat
    # vertical sur la gauche dont la hauteur dépasse 2× la profondeur.
    if variant in ("v1", "v4"):
        # Côté droit
        right_candidates = [i for i, orient in enumerate(orientations)
                            if i not in skip_indices and orient == 'vert' and cx_list[i] > mid_x and heights[i] > 2 * prof]
        if right_candidates:
            # Si l'un dépasse 3× la profondeur, on sélectionne le plus haut
            gt = [i for i in right_candidates if heights[i] > 3 * prof]
            if gt:
                idx = max(gt, key=lambda i: heights[i])
            else:
                idx = min(right_candidates, key=lambda i: cy_list[i])
            bridging_vert_indices.add(idx)
        # Côté gauche (uniquement pour v4)
        if variant == "v4":
            left_candidates = [i for i, orient in enumerate(orientations)
                               if i not in skip_indices and orient == 'vert' and cx_list[i] <= mid_x and heights[i] > 2 * prof]
            if len(left_candidates) == 1:
                bridging_vert_indices.add(left_candidates[0])

    # Détection des horizontaux à ajuster pour la variante v3 : choisir
    # parmi les dossiers horizontaux dont la largeur est au moins 2×
    # la profondeur celui ayant le centre x le plus petit (le plus à
    # gauche).  Il sera réduit à ``prof + thk``.
    if variant == "v3":
        candidates = [i for i, orient in enumerate(orientations)
                      if i not in skip_indices and orient == 'horiz' and widths[i] >= 2 * prof]
        if candidates:
            idx = min(candidates, key=lambda i: cx_list[i])
            bridging_horiz[idx] = 'v3'

    # Détection des horizontaux à ajuster pour la variante v2 : choisir
    # le dossier horizontal dont la largeur dépasse 2× la profondeur.  On
    # choisit celui dont la largeur est maximale (en général un seul dossier
    # correspond) et on lui retirera une profondeur pour le calcul de sa
    # longueur.
    if variant == "v2":
        candidates = [i for i, orient in enumerate(orientations)
                      if i not in skip_indices and orient == 'horiz' and widths[i] > 2 * prof]
        if candidates:
            idx = max(candidates, key=lambda i: widths[i])
            bridging_horiz[idx] = 'v2'

    total = 0.0
    for idx, (width, height, orient) in enumerate(zip(widths, heights, orientations)):
        if idx in skip_indices:
            continue
        # Calculer la longueur corrigée
        if idx in bridging_vert_indices:
            # Vertical bridging : longueur = profondeur + (épaisseur si dossier bas)
            if prof > 0:
                longueur = prof + (thk if dossier_bas_present else 0)
            else:
                longueur = height
        elif idx in bridging_horiz:
            if bridging_horiz[idx] == 'v3':
                # Variante v3 : longueur = profondeur + (épaisseur si dossier bas)
                if prof > 0:
                    longueur = prof + (thk if dossier_bas_present else 0)
                else:
                    longueur = width
            else:
                # Variante v2 : retirer une profondeur
                longueur = max(width - prof, 0)
        else:
            if orient == 'horiz':
                if prof and width > 3 * prof:
                    # Grand dossier horizontal en « L » : longueur = profondeur
                    longueur = prof
                elif prof and (2 * prof < width <= 3 * prof) and count_prof_horiz >= 2:
                    longueur = width - prof
                else:
                    longueur = width
            else:
                # Vertical
                if prof and height > 3 * prof:
                    longueur = prof + (thk if dossier_bas_present else 0)
                else:
                    longueur = height
        # Pondération du dossier
        if longueur <= 110:
            total += 0.5
        else:
            total += 1.0
    return total

# -------------------------------------------------------------------------
# Affichage détaillé des dimensions des dossiers (debug)
# -------------------------------------------------------------------------
def _print_dossiers_dimensions(polys):
    """
    Affiche pour chaque dossier ses dimensions de bounding box
    et la longueur utilisée pour le comptage pondéré.

    Cette fonction utilise une heuristique pour déterminer la longueur
    réellement pertinente des dossiers lorsque ceux‑ci sont composés de
    formes en « L » ou couvrent plusieurs tronçons.  Dans certaines
    variantes du canapé en U, des dossiers sont générés comme des
    polygones non rectangulaires dont la diagonale couvre une portion
    supplémentaire du canapé (par exemple, sur la branche droite ou
    sous l'assise).  La valeur par défaut, qui prend le plus grand côté
    de la boîte englobante, conduit alors à des longueurs erronées.

    L'algorithme suivant est appliqué :

    * On estime la profondeur de l'assise (``prof``) en prenant le
      maximum des petites dimensions (largeur ou hauteur) des polygones
      d'assise.  Cette profondeur est constante pour un canapé donné.
    * On estime l'épaisseur commune des dossiers (``thk``) en prenant
      la plus petite des petites dimensions des polygones de dossier.
      Typiquement cette valeur vaut 10 cm lorsqu'un dossier est présent.
    * On détermine la liste des largeurs des dossiers orientés
      horizontalement (largeur > hauteur) afin de compter combien
      correspondent exactement à la profondeur (``prof``).  Cette
      information sert à différencier certaines variantes où la partie
      horizontale d'un dossier chevauche la méridienne.
    * Pour chaque dossier :
      - si le dossier est horizontal (largeur > hauteur) :
        - lorsqu'il couvre plus de trois fois la profondeur
          (``largeur > 3*prof``), la longueur prise en compte est
          considérée comme la profondeur.  C'est le cas des grands
          dossiers « en L » qui recouvrent la gauche et la droite.
        - lorsqu'il couvre entre deux et trois fois la profondeur
          (``2*prof < largeur <= 3*prof``) et qu'au moins deux autres
          dossiers horizontaux ont une largeur égale à la profondeur,
          on retire une profondeur à la largeur afin d'ignorer la
          partie qui déborde sur la branche droite.  Ce cas survient
          notamment dans la variante v2 où un dossier horizontal
          comprend une partie au‑delà de l'accoudoir.
        - dans les autres cas, la longueur prise en compte est la
          largeur.
      - si le dossier est vertical (largeur <= hauteur) :
        - lorsqu'il couvre plus de trois fois la profondeur
          (``hauteur > 3*prof``), on considère que la partie
          réellement utile correspond à la profondeur plus l'épaisseur
          du dossier.  Cela corrige les dossiers « en L » situés sur
          les branches verticales gauche ou droite des variantes v1/v4.
        - sinon, on prend simplement la hauteur.

    Le poids (nombre de dossiers pondéré) est alors calculé avec
    ``0.5`` pour une longueur prise en compte ≤ 110 cm, sinon ``1.0``.
    """
    print("Détail des dossiers (dimensions bounding box) :")
    dossiers = polys.get("dossiers") or []
    if not dossiers:
        print("  (aucun dossier)")
        return

    # Estime la profondeur d'assise (prof) et l'épaisseur des dossiers (thk)
    # en analysant respectivement les polygones d'assise et de dossier.
    prof_candidates = []
    for bp in polys.get("banquettes", []):
        xs_b = [pt[0] for pt in bp]
        ys_b = [pt[1] for pt in bp]
        w_b = max(xs_b) - min(xs_b)
        h_b = max(ys_b) - min(ys_b)
        prof_candidates.append(min(w_b, h_b))
    prof = max(prof_candidates) if prof_candidates else 0
    thk_candidates = []
    for dp in dossiers:
        xs_d = [pt[0] for pt in dp]
        ys_d = [pt[1] for pt in dp]
        w_d = max(xs_d) - min(xs_d)
        h_d = max(ys_d) - min(ys_d)
        m = min(w_d, h_d)
        if m > 0:
            thk_candidates.append(m)
    thk = min(thk_candidates) if thk_candidates else 0

    # Déterminer la variante et la présence d'un dossier bas
    variant = polys.get("__variant")
    dossier_bas_present = bool(polys.get("__dossier_bas", False))
    dossier_left_present = bool(polys.get("__dossier_left", True))
    dossier_right_present = bool(polys.get("__dossier_right", True))

    # Préparer des métriques pour chaque dossier : largeur, hauteur, centre et orientation
    widths = []  # largeur de la boîte englobante
    heights = []  # hauteur de la boîte englobante
    cx_list = []  # centre x
    cy_list = []  # centre y
    orientations = []  # 'horiz' ou 'vert'
    for dp in dossiers:
        xs_d = [pt[0] for pt in dp]
        ys_d = [pt[1] for pt in dp]
        w_d = max(xs_d) - min(xs_d)
        h_d = max(ys_d) - min(ys_d)
        widths.append(w_d)
        heights.append(h_d)
        cx_list.append(sum(xs_d) / float(len(xs_d)))
        cy_list.append(sum(ys_d) / float(len(ys_d)))
        orientations.append('horiz' if w_d > h_d else 'vert')

    # Déterminer la liste des côtés pour chaque dossier pour filtrer ceux qui
    # ne doivent pas être pris en compte.  Si cette information est
    # absente, on suppose que tous les dossiers sont autorisés.
    dossier_sides = polys.get("dossiers_sides")
    # Calculer les indices à ignorer selon la présence des dossiers
    skip_indices = set()
    if dossier_sides:
        for i, side in enumerate(dossier_sides):
            if side == "left" and not dossier_left_present:
                skip_indices.add(i)
            elif side == "right" and not dossier_right_present:
                skip_indices.add(i)
            elif side == "bottom" and not dossier_bas_present:
                skip_indices.add(i)
    # Supprimer également les pièces horizontales résiduelles lorsque le dossier bas est absent.
    # Ces pièces ont une hauteur très faible (≤ épaisseur) et ne représentent pas un vrai dossier.
    if not dossier_bas_present:
        for i, orient in enumerate(orientations):
            if orient == 'horiz' and i not in skip_indices:
                if thk and heights[i] <= thk + 1e-6:
                    skip_indices.add(i)

    # Évaluer la position médiane en x pour séparer gauche/droite.  On se
    # base sur l'ensemble des banquettes car elles couvrent toute la
    # largeur du canapé.
    xs_all = []
    for bp in polys.get("banquettes", []):
        for (x, _) in bp:
            xs_all.append(x)
    mid_x = (min(xs_all) + max(xs_all)) / 2.0 if xs_all else 0.0

    # Compter les dossiers horizontaux dont la largeur est égale à la profondeur
    count_prof_horiz = 0
    for idx, (w_d, h_d) in enumerate(zip(widths, heights)):
        if idx in skip_indices:
            continue
        if w_d > h_d and abs(w_d - prof) < 1e-6:
            count_prof_horiz += 1

    # Détecter les dossiers « bridging » selon la variante.  Un dossier
    # "vertical bridging" relie le bas et le côté droit/gauche et doit
    # être réduit à une longueur de ``prof + thk``.  Un dossier
    # "horizontal bridging" dans la variante v3 est réduit à ``prof + thk``.
    # Dans la variante v2, un dossier horizontal trop long est réduit de
    # ``prof`` (retirer la profondeur excédentaire) et sa longueur
    # considérée est « largeur – prof ».  Les indices sont enregistrés
    # dans des structures distinctes pour pouvoir appliquer des règles
    # spécifiques lors du calcul de la longueur.
    bridging_vert_indices = set()
    bridging_horiz = {}
    # Détection des verticaux à ajuster (variants v1 et v4).  Uniquement
    # sur le côté droit pour v1 et v4, et également sur le côté gauche
    # pour v4 lorsque la branche gauche est plus haute que la branche
    # droite.
    if variant in ("v1", "v4"):
        # Côté droit : choisir le dossier vertical avec cx > mid_x et
        # hauteur > 2*prof, en excluant ceux à ignorer.
        right_candidates = [i for i, orient in enumerate(orientations)
                            if i not in skip_indices and orient == 'vert' and cx_list[i] > mid_x and heights[i] > 2 * prof]
        if right_candidates:
            # Vérifier s'il existe une grande hauteur > 3*prof
            gt = [i for i in right_candidates if heights[i] > 3 * prof]
            if gt:
                idx = max(gt, key=lambda i: heights[i])
            else:
                idx = min(right_candidates, key=lambda i: cy_list[i])
            bridging_vert_indices.add(idx)
        # Dans la variante v4, un dossier vertical « bridging » peut
        # également exister sur la gauche, mais uniquement s'il n'y a
        # qu'un seul dossier vertical suffisamment haut sur ce côté.
        if variant == "v4":
            left_candidates = [i for i, orient in enumerate(orientations)
                               if i not in skip_indices and orient == 'vert' and cx_list[i] <= mid_x and heights[i] > 2 * prof]
            if len(left_candidates) == 1:
                bridging_vert_indices.add(left_candidates[0])

    # Détection des horizontaux à ajuster pour la variante v3 : choisir
    # parmi les dossiers horizontaux dont la largeur est au moins 2×
    # la profondeur celui ayant le centre x le plus petit (le plus à
    # gauche).  Il sera réduit à ``prof + thk``.
    if variant == "v3":
        candidates = [i for i, orient in enumerate(orientations)
                      if i not in skip_indices and orient == 'horiz' and widths[i] >= 2 * prof]
        if candidates:
            idx = min(candidates, key=lambda i: cx_list[i])
            bridging_horiz[idx] = 'v3'

    # Détection des horizontaux à ajuster pour la variante v2 : choisir
    # le dossier horizontal dont la largeur dépasse 2× la profondeur.
    if variant == "v2":
        candidates = [i for i, orient in enumerate(orientations)
                      if i not in skip_indices and orient == 'horiz' and widths[i] > 2 * prof]
        if candidates:
            # Choisir celui dont la largeur est maximale (en général un
            # seul dossier correspond)
            idx = max(candidates, key=lambda i: widths[i])
            bridging_horiz[idx] = 'v2'

    # Affichage détaillé de chaque dossier.  On renumérote les dossiers
    # affichés en omettant ceux marqués comme ignorés.
    printed_idx = 1
    for idx, (width, height, cx, cy, orient) in enumerate(zip(widths, heights, cx_list, cy_list, orientations)):
        if idx in skip_indices:
            continue
        # Calcul de la longueur corrigée selon le cas
        if idx in bridging_vert_indices:
            # Dossier vertical reliant le bas : longueur = profondeur + (épaisseur si dossier bas)
            if prof > 0:
                longueur = prof + (thk if dossier_bas_present else 0)
            else:
                longueur = height
        elif idx in bridging_horiz:
            # Dossier horizontal à ajuster selon la variante
            if bridging_horiz[idx] == 'v3':
                # Variante v3 : longueur réduite à profondeur + (épaisseur si dossier bas)
                if prof > 0:
                    longueur = prof + (thk if dossier_bas_present else 0)
                else:
                    longueur = width
            else:
                # Variante v2 : retirer une profondeur
                longueur = max(width - prof, 0)
        else:
            # Cas générique suivant l'orientation et les heuristiques
            if orient == 'horiz':
                if prof and width > 3 * prof:
                    longueur = prof
                elif prof and (2 * prof < width <= 3 * prof) and count_prof_horiz >= 2:
                    longueur = width - prof
                else:
                    longueur = width
            else:
                # vertical
                if prof and height > 3 * prof:
                    longueur = prof + (thk if dossier_bas_present else 0)
                else:
                    longueur = height
        # Déterminer le poids en fonction de la longueur corrigée
        poids = 0.5 if longueur <= 110 else 1.0
        # Déterminer les dimensions à afficher.  Par défaut on
        # remplace la dimension principale (la plus grande) par la
        # longueur corrigée afin d'éviter de signaler des tailles
        # trompeuses dues aux formes en « L ».  Dans certains cas de
        # dossiers "bridging", seuls les dossiers sur le côté droit
        # voient leur dimension affichée modifiée ; ceux du côté gauche
        # conservent leur taille réelle afin de préserver la
        # compréhension des segments.
        if orient == 'horiz':
            # Dossier horizontal : largeur → longueur corrigée
            affiche_L = longueur
            # Hauteur affichée = hauteur réelle ; si nulle ou très petite,
            # utiliser l'épaisseur commune des dossiers (thk) comme valeur de secours
            affiche_P = height if height > 0 else thk
        else:
            # Dossier vertical
            if idx in bridging_vert_indices and cx > mid_x:
                # Côté droit : afficher la hauteur corrigée
                affiche_L = width
                affiche_P = longueur
            elif idx in bridging_vert_indices and cx <= mid_x:
                # Côté gauche : conserver la hauteur d'origine
                affiche_L = width
                # Hauteur affichée = hauteur réelle ; si nulle, utiliser thk
                affiche_P = height if height > 0 else thk
            else:
                # Cas générique vertical : afficher la longueur corrigée
                affiche_L = width
                affiche_P = longueur
        # Affiche les dimensions en arrondissant à l'entier le plus proche
        print(
            f"  Dossier {printed_idx} : {int(round(affiche_L))}×{int(round(affiche_P))} cm "
            f"(longueur prise en compte = {int(round(longueur))} cm → {poids} dossier)"
        )
        printed_idx += 1

# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U2f
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U2f(banquette_labels, banquette_sizes, angle_sizes,
                                   dossier_left, dossier_bas, dossier_right,
                                   meridienne_side=None, meridienne_len=0):
    """
    Affiche les dimensions des dossiers pour les canapés U2F en se basant
    directement sur les longueurs des mousses (banquettes et angles). Les
    longueurs sont exprimées en centimètres et multipliées par l’épaisseur
    commune des dossiers (10 cm). Les suffixes « bis » désignent le second
    morceau d’une même branche lorsqu’il y a scission.

    Paramètres
    ----------
    banquette_labels : liste de str
        Étiquettes des morceaux d’assise, par exemple « 1 », « 1-bis », « 2 »,
        « 2-bis », « 3 », « 3-bis ».
    banquette_sizes : liste de tuples
        Chaque tuple (L, P) contient la longueur L et la profondeur P (P n’est
        pas utilisée ici) des mousses d’assise correspondant à
        ``banquette_labels``.
    angle_sizes : liste d’int
        Longueurs des mousses d’angle (première dimension retournée par
        ``banquette_dims``) dans l’ordre : angle 1, angle 2.
    dossier_left, dossier_bas, dossier_right : bool
        Indiquent la présence des dossiers sur les côtés gauche, bas et droit.
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {}
    for lab, (L, _P) in zip(banquette_labels, banquette_sizes):
        label_to_len[lab] = int(L)
    # Ajuster les longueurs en fonction de la méridienne.  Si une
    # méridienne est positionnée sur le côté droit (``meridienne_side`` = 'd'),
    # on retranche sa longueur au dossier 3 (ou 3-bis si ce dossier
    # est scindé).  Si elle est sur le côté gauche (``meridienne_side`` = 'g'),
    # on retranche la longueur au dossier 1 (ou 1-bis).
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        # Branche droite
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        # Branche gauche
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)
    # Côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        if "1" in label_to_len:
            print(f"  Dossier 1= {label_to_len['1']}x10cm")
        if "1-bis" in label_to_len:
            print(f"  Dossier 1 bis = {label_to_len['1-bis']}x10cm")
        if angle_sizes:
            # Ajout de 10 cm pour les dossiers reliant le bas
            val = angle_sizes[0] + (10 if dossier_bas else 0)
            print(f"  Dossier Ang 1 gauche = {val}x10cm")
    # Côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        if angle_sizes:
            print(f"  Dossier Ang 1 bas = {angle_sizes[0]}x10cm")
        if "2" in label_to_len:
            print(f"  Dossier 2 = {label_to_len['2']}x10cm")
        if "2-bis" in label_to_len:
            print(f"  Dossier 2 bis = {label_to_len['2-bis']}x10cm")
        if len(angle_sizes) > 1:
            print(f"  Dossier Angle 2 bas = {angle_sizes[1]}x10cm")
    # Côté droite
    if dossier_right:
        print("Dossiers Côté droite :")
        if len(angle_sizes) > 1:
            val = angle_sizes[1] + (10 if dossier_bas else 0)
            print(f"  Dossier Ang droite 2 = {val}x10cm")
        if "3" in label_to_len:
            print(f"  Dossier 3 = {label_to_len['3']}x10cm")
        if "3-bis" in label_to_len:
            print(f"  Dossier 3 bis = {label_to_len['3-bis']}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U v1 (sans angles)
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U_v1(banquette_labels, banquette_sizes,
                                    profondeur, dossier_left, dossier_bas, dossier_right,
                                    meridienne_side=None, meridienne_len=0):
    """
    Affiche les dimensions des dossiers pour les canapés en U variant v1 (sans
    banquettes d'angle). Cette version se base uniquement sur les longueurs
    des mousses d'assise (première dimension) et sur la profondeur du canapé.

    La répartition est la suivante :

      * **Côté gauche** : dossiers 1 et 1 bis (si scission) correspondent aux
        segments de la banquette gauche.  Lorsque la banquette gauche est
        munie d’une méridienne, la longueur de la méridienne est soustraite au
        dossier concerné (le second morceau s’il y en a deux, sinon le
        premier).

      * **Côté bas** : dossier 2 représente le retour vertical (épaisseur de
        l’assise) situé entre la branche gauche et la branche centrale. Sa
        longueur est égale à la profondeur de l’assise si le dossier bas est
        absent, ou à la profondeur augmentée de 10 cm si un dossier bas est
        présent.  Les dossiers 3 et 3 bis correspondent aux segments de la
        banquette centrale (bas) lorsqu’un dossier bas est présent. Si le
        dossier bas est absent, ces segments ne sont pas affichés.

      * **Côté droite** : dossier 4 est le retour vertical situé entre la
        branche centrale et la branche droite, avec la même logique que
        dossier 2 pour la longueur.  Les dossiers 5 et 5 bis correspondent
        aux segments de la banquette droite.  Si une méridienne est
        positionnée sur le côté droit, sa longueur est soustraite au dossier
        concerné (le second morceau s’il y en a deux, sinon le premier).

    Tous les dossiers sont exprimés en centimètres, avec l’épaisseur
    constante de 10 cm ; ainsi une longueur de ``L`` est affichée sous la
    forme ``Lx10cm``.

    Paramètres
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (par exemple « 1 », « 1-bis »,
        « 2 », « 2-bis », « 3 », « 3-bis »).
    banquette_sizes : list of tuples
        Chaque tuple ``(L, P)`` contient la longueur ``L`` et la profondeur
        ``P`` des mousses d’assise correspondant aux ``banquette_labels``.
    profondeur : int
        Profondeur de l’assise (en cm).
    dossier_left, dossier_bas, dossier_right : bool
        Indiquent si un dossier est présent respectivement sur la branche
        gauche, bas ou droite.  Les dossiers d’un côté ne sont affichés que
        si le dossier correspondant est présent.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'d'`` pour une méridienne à
        droite, ``None`` sinon.
    meridienne_len : int
        Longueur de la méridienne en centimètres.  Si nulle, aucune
        soustraction n’est appliquée.
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}
    # Ajuster les longueurs selon la méridienne sur la gauche
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        # S'il y a une scission sur la branche gauche, on retire la méridienne
        # du second morceau (label « 1-bis »).  Sinon, on le retire du
        # premier morceau.
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)
    # Ajuster les longueurs selon la méridienne sur la droite
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)


def _print_dossiers_dimensions_U_v2(
    banquette_labels,
    banquette_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour les canapés en U variante v2
    (sans angles). Cette variante se distingue par les règles suivantes :

      * Le dossier 1 (premier morceau de la branche gauche) gagne +10 cm
        lorsque le dossier bas est présent.  Le morceau scindé 1‑bis n’est
        pas augmenté.
      * Les retours verticaux « Dossier 2 » et « Dossier 4 » appartiennent au
        côté bas et mesurent toujours la profondeur de l’assise, sans
        augmentation de 10 cm.
      * Le dossier 5 (premier morceau de la branche droite) est majoré de
        +10 cm lorsque le dossier bas est présent.  Le morceau scindé 5‑bis
        n’est pas augmenté.
      * Les morceaux horizontaux du bas (dossiers 3 et 3 bis) ne sont
        affichés que si un dossier bas est présent.
      * Les longueurs des dossiers peuvent être réduites par une méridienne
        selon les règles suivantes : la réduction s’applique au morceau
        principal s’il n’y a pas de « bis », sinon au « bis ».

    Paramètres
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (par exemple « 1 », « 1-bis »,
        « 2 », « 2-bis », « 3 », « 3-bis »).
    banquette_sizes : list of tuples
        Chaque tuple ``(L, P)`` contient la longueur ``L`` et la profondeur
        ``P`` des mousses d’assise correspondant aux ``banquette_labels``.
    profondeur : int
        Profondeur de l’assise (en cm).
    dossier_left, dossier_bas, dossier_right : bool
        Indiquent si un dossier est présent respectivement sur la branche
        gauche, bas ou droite.  Les dossiers d’un côté ne sont affichés
        que si le dossier correspondant est présent.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'d'`` pour une méridienne à
        droite, ``None`` sinon.
    meridienne_len : int
        Longueur de la méridienne en centimètres.  Si nulle, aucune
        soustraction n’est appliquée.
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}
    # Ajuster les longueurs selon la méridienne sur la gauche
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)
    # Ajuster les longueurs selon la méridienne sur la droite
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)
    # --------------------------------------------------------------------
    # CÔTÉ GAUCHE
    #
    # Affichage des dossiers sur la branche gauche.  Le dossier 1 est
    # augmenté de 10 cm lorsque le dossier bas est présent.  Le dossier 1 bis
    # (en cas de scission) n'est pas augmenté.  Aucun retour vertical
    # n'est affiché sur le côté gauche dans la variante v2 (les retours
    # verticaux appartiennent au côté bas).
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1 : premier morceau de la banquette gauche
        if '1' in label_to_len:
            length1 = label_to_len['1'] + (10 if dossier_bas else 0)
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis : second morceau de la banquette gauche (non augmenté)
        if '1-bis' in label_to_len:
            print(f"  Dossier 1 bis = {label_to_len['1-bis']}x10cm")

    # --------------------------------------------------------------------
    # CÔTÉ BAS
    #
    # Les dossiers du côté bas sont affichés uniquement si le dossier bas
    # est présent.  Ils regroupent :
    #   - Dossier 2 : retour vertical gauche → longueur = profondeur ;
    #   - Dossier 3 et Dossier 3 bis : morceaux horizontaux de la banquette
    #     centrale (affichés uniquement s'ils existent) ;
    #   - Dossier 4 : retour vertical droit → longueur = profondeur.
    if dossier_bas:
        bottom_lines = []
        # Dossier 2 : retour vertical gauche
        bottom_lines.append(f"Dossier 2 = {int(profondeur)}x10cm")
        # Dossiers 3 / 3 bis : morceaux horizontaux de la banquette centrale
        if '2' in label_to_len:
            bottom_lines.append(f"Dossier 3 = {label_to_len['2']}x10cm")
        if '2-bis' in label_to_len:
            bottom_lines.append(f"Dossier 3 bis = {label_to_len['2-bis']}x10cm")
        # Dossier 4 : retour vertical droit
        bottom_lines.append(f"Dossier 4 = {int(profondeur)}x10cm")
        if bottom_lines:
            print("Dossiers Côté bas :")
            for line in bottom_lines:
                print(f"  {line}")

    # --------------------------------------------------------------------
    # CÔTÉ DROITE
    #
    # Les dossiers du côté droit regroupent les morceaux horizontaux de la
    # banquette droite (dossiers 5 et 5 bis).  Le dossier 5 est augmenté
    # de 10 cm lorsque le dossier bas est présent, tandis que le 5 bis
    # conserve sa longueur d'origine.  Ces éléments ne sont affichés que
    # si un dossier droit est présent.
    if dossier_right:
        right_lines = []
        if '3' in label_to_len:
            length5 = label_to_len['3'] + (10 if dossier_bas else 0)
            right_lines.append(f"Dossier 5 = {length5}x10cm")
        if '3-bis' in label_to_len:
            right_lines.append(f"Dossier 5 bis = {label_to_len['3-bis']}x10cm")
        if right_lines:
            print("Dossiers Côté droite :")
            for line in right_lines:
                print(f"  {line}")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U v3 (sans angles)
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U_v3(
    banquette_labels,
    banquette_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour les canapés en U variante v3.

    Cette version se base uniquement sur les longueurs des mousses d’assise
    (longueurs des banquettes) et sur la profondeur du canapé.  Les dossiers
    sont regroupés par côté (gauche, bas, droite) en suivant les règles
    décrites ci‑dessous :

      * **Côté gauche** : Dossier 1 et Dossier 1 bis correspondent aux
        morceaux de la banquette gauche (labels « 1 » et « 1-bis »).  La
        longueur du dossier est celle de la mousse.  Lorsqu’une méridienne
        est positionnée sur le côté gauche (``meridienne_side`` = « g »), la
        longueur de la méridienne est soustraite soit du morceau « 1-bis » si
        celui‑ci existe, soit du morceau « 1 » sinon.  Le Dossier 2 est le
        retour vertical entre la branche gauche et la branche basse ; sa
        longueur vaut la profondeur de l’assise augmentée de 10 cm lorsque
        ``dossier_bas`` est vrai, sinon la profondeur seule.

      * **Côté bas** : Dossier 3 et Dossier 3 bis correspondent aux morceaux
        horizontaux de la banquette centrale (labels « 2 » et « 2-bis »).
        Ces longueurs ne sont jamais modifiées par la méridienne.  Dossier 4
        est le retour vertical entre la branche centrale et la branche droite ;
        sa longueur est toujours égale à la profondeur de l’assise (sans
        augmentation de 10 cm).

      * **Côté droite** : Dossier 5 et Dossier 5 bis correspondent aux
        morceaux de la banquette droite (labels « 3 » et « 3-bis »).  La
        longueur du morceau principal « 3 » est augmentée de 10 cm lorsque
        ``dossier_bas`` est vrai.  Si une méridienne est positionnée sur le
        côté droit (``meridienne_side`` = « d »), la longueur de la
        méridienne est soustraite au morceau « 3-bis » s’il existe, sinon au
        morceau « 3 ».  Le morceau « 3-bis » (Dossier 5 bis) ne reçoit jamais
        l’augmentation de 10 cm.

    Tous les dossiers sont exprimés en centimètres, avec une épaisseur
    constante de 10 cm (affichage sous la forme « Lx10cm »).

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (par exemple « 1 », « 1-bis »,
        « 2 », « 2-bis », « 3 », « 3-bis »).
    banquette_sizes : list of tuples
        Chaque tuple ``(L, P)`` contient la longueur ``L`` et la profondeur
        ``P`` des mousses d’assise correspondant aux ``banquette_labels``.
    profondeur : int
        Profondeur de l’assise (en cm).
    dossier_left, dossier_bas, dossier_right : bool
        Indiquent si un dossier est présent respectivement sur la branche
        gauche, bas ou droite.  Les dossiers d’un côté ne sont affichés
        que si le dossier correspondant est présent.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'d'`` pour une méridienne à
        droite, ``None`` sinon.
    meridienne_len : int
        Longueur de la méridienne en centimètres.  Si nulle, aucune
        soustraction n’est appliquée.
    """
    # Construire un dictionnaire label → longueur principale (L) pour les
    # morceaux d’assise.  On effectue une copie explicite des longueurs afin
    # de pouvoir les ajuster selon la méridienne sans modifier l’entrée.
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Ajuster les longueurs selon la méridienne sur la gauche.  La réduction
    # s’applique uniquement aux dossiers du côté gauche et seulement si le
    # dossier correspondant est présent.  La longueur de la méridienne est
    # retirée du morceau « 1-bis » lorsqu’il existe, sinon du morceau « 1 ».
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Ajuster les longueurs selon la méridienne sur la droite.  La réduction
    # s’applique aux dossiers du côté droit uniquement.  On retire la
    # longueur de la méridienne du morceau « 3-bis » lorsqu’il existe, sinon
    # du morceau « 3 ».
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)

    # Impression des dossiers du côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1 : premier morceau de la banquette gauche
        if '1' in label_to_len:
            length1 = label_to_len['1']
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis : second morceau de la banquette gauche
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")
        # Dossier 2 : retour vertical gauche
        # Sa longueur est égale à la profondeur, augmentée de 10 cm lorsque
        # le dossier bas est présent.
        length2 = int(profondeur) + (10 if dossier_bas else 0)
        print(f"  Dossier 2 = {length2}x10cm")

    # Impression des dossiers du côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 3 : premier morceau de la banquette centrale
        if '2' in label_to_len:
            length3 = label_to_len['2']
            print(f"  Dossier 3 = {length3}x10cm")
        # Dossier 3 bis : second morceau de la banquette centrale
        if '2-bis' in label_to_len:
            length3bis = label_to_len['2-bis']
            print(f"  Dossier 3 bis = {length3bis}x10cm")
        # Dossier 4 : retour vertical droit de la branche centrale
        # Sa longueur est toujours la profondeur, sans augmentation.
        length4 = int(profondeur)
        print(f"  Dossier 4 = {length4}x10cm")

    # Impression des dossiers du côté droit
    if dossier_right:
        print("Dossiers Côté droite :")
        # Dossier 5 : premier morceau de la banquette droite
        if '3' in label_to_len:
            length5 = label_to_len['3'] + (10 if dossier_bas else 0)
            print(f"  Dossier 5 = {length5}x10cm")
        # Dossier 5 bis : second morceau de la banquette droite (non augmenté)
        if '3-bis' in label_to_len:
            length5bis = label_to_len['3-bis']
            print(f"  Dossier 5 bis = {length5bis}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U v4 (sans angles)
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U_v4(
    banquette_labels,
    banquette_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour les canapés en U variante v4.

    Cette version se base uniquement sur les longueurs des mousses d’assise
    (longueurs des banquettes) et sur la profondeur du canapé.  Les dossiers
    sont regroupés par côté (gauche, bas, droite) en suivant les règles
    spécifiques de la variante v4 :

      * **Côté gauche** : Dossier 1 correspond au premier morceau de la
        banquette gauche (label « 1 ») et est augmenté de 10 cm lorsque le
        dossier bas est présent.  Lorsqu’une méridienne est positionnée sur
        la gauche (``meridienne_side`` = « g »), la longueur de la
        méridienne est soustraite au morceau « 1 » s’il n’y a pas de scission,
        sinon au morceau « 1-bis ».  Le Dossier 1 bis (label « 1-bis ») n’est
        pas augmenté de 10 cm et voit sa longueur réduite de la méridienne
        uniquement s’il y a une méridienne à gauche.

      * **Côté bas** : Dossier 2 est le retour vertical entre les branches
        gauche et centrale et mesure toujours la profondeur de l’assise (sans
        augmentation de 10 cm).  Les Dossiers 3 et 3 bis correspondent aux
        morceaux horizontaux de la banquette centrale (labels « 2 » et
        « 2-bis ») et ne sont jamais modifiés, même en présence d’une
        méridienne.

      * **Côté droite** : Dossier 4 est le retour vertical entre les
        branches centrale et droite.  Sa longueur est égale à la profondeur
        augmentée de 10 cm lorsque le dossier bas est présent, sinon la
        profondeur seule.  Les Dossiers 5 et 5 bis correspondent aux
        morceaux de la banquette droite (labels « 3 » et « 3-bis ») et ne
        bénéficient d’aucune augmentation de 10 cm.  En présence d’une
        méridienne sur la droite (``meridienne_side`` = « d »), la longueur
        de la méridienne est soustraite au morceau « 3 » lorsqu’il n’y a pas
        de scission, sinon au morceau « 3-bis ».

    Tous les dossiers sont exprimés en centimètres, avec une épaisseur
    constante de 10 cm (affichage sous la forme « Lx10cm »).

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (par exemple « 1 », « 1-bis »,
        « 2 », « 2-bis », « 3 », « 3-bis »).
    banquette_sizes : list of tuples
        Chaque tuple ``(L, P)`` contient la longueur ``L`` et la profondeur
        ``P`` des mousses d’assise correspondant aux ``banquette_labels``.
    profondeur : int
        Profondeur de l’assise (en cm).
    dossier_left, dossier_bas, dossier_right : bool
        Indiquent si un dossier est présent respectivement sur la branche
        gauche, bas ou droite.  Les dossiers d’un côté ne sont affichés
        que si le dossier correspondant est présent.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'d'`` pour une méridienne à
        droite, ``None`` sinon.
    meridienne_len : int
        Longueur de la méridienne en centimètres.  Si nulle, aucune
        soustraction n’est appliquée.
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Ajuster les longueurs selon la méridienne sur la gauche.  On retire
    # la longueur de la méridienne soit du morceau « 1-bis » s’il existe,
    # soit du morceau « 1 ».
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Ajuster les longueurs selon la méridienne sur la droite.  La réduction
    # s’applique au morceau « 3-bis » lorsqu’il existe, sinon au morceau « 3 ».
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)

    # Impression des dossiers du côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1 : premier morceau de la banquette gauche, augmenté de
        # 10 cm lorsque le dossier bas est présent.
        if '1' in label_to_len:
            length1 = label_to_len['1'] + (10 if dossier_bas else 0)
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis : second morceau de la banquette gauche (non augmenté)
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")

    # Impression des dossiers du côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 2 : retour vertical gauche, longueur = profondeur
        length2 = int(profondeur)
        print(f"  Dossier 2 = {length2}x10cm")
        # Dossiers 3 / 3 bis : morceaux de la banquette centrale
        if '2' in label_to_len:
            length3 = label_to_len['2']
            print(f"  Dossier 3 = {length3}x10cm")
        if '2-bis' in label_to_len:
            length3bis = label_to_len['2-bis']
            print(f"  Dossier 3 bis = {length3bis}x10cm")

    # Impression des dossiers du côté droit
    if dossier_right:
        print("Dossiers Côté droite :")
        # Dossier 4 : retour vertical droit, profondeur + 10 cm lorsque le
        # dossier bas est présent
        length4 = int(profondeur) + (10 if dossier_bas else 0)
        print(f"  Dossier 4 = {length4}x10cm")
        # Dossier 5 : premier morceau de la banquette droite (non augmenté)
        if '3' in label_to_len:
            length5 = label_to_len['3']
            print(f"  Dossier 5 = {length5}x10cm")
        # Dossier 5 bis : second morceau de la banquette droite
        if '3-bis' in label_to_len:
            length5bis = label_to_len['3-bis']
            print(f"  Dossier 5 bis = {length5bis}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U1F v1
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U1F_v1(
    banquette_labels,
    banquette_sizes,
    angle_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour la variante U1F v1.

    La catégorisation des dossiers ne se base que sur les étiquettes
    logiques des morceaux d’assise (``1``, ``1-bis``, ``2``, ``2-bis``,
    ``3``, ``3-bis``).  La géométrie (vertical/horizontale, coin, etc.)
    est ignorée : seul le côté (gauche, bas, droite) auquel les morceaux
    appartiennent compte, déterminé par la présence des booléens
    ``dossier_left``, ``dossier_bas`` et ``dossier_right``.

    Les règles appliquées sont les suivantes :

      * **Côté gauche** : Dossier 1 utilise la longueur du morceau
        ``1`` telle quelle (sans ajout).  Si une méridienne est
        présente à gauche et qu’il n’y a pas de scission (pas de
        ``1-bis``), on retranche la longueur de la méridienne de ce
        morceau.  Le Dossier 1 bis (étiquette ``1-bis``) est affiché
        séparément et voit sa longueur réduite de la méridienne le cas
        échéant.  Enfin, un Dossier 1 angle correspondant au côté
        vertical de l’angle est affiché ; sa longueur est égale à la
        dimension d’angle et augmente de 10 cm lorsque le dossier bas
        est présent.

      * **Côté bas** : Dossier 2 angle correspond au côté horizontal de
        l’angle et a une longueur égale à la dimension d’angle sans
        augmentation.  Dossier 2 et Dossier 2 bis correspondent aux
        morceaux d’assise « 2 » et « 2-bis » et ne subissent aucune
        modification.  Dossier 3 est un retour vertical et sa longueur
        vaut la profondeur du canapé (``profondeur``).

      * **Côté droite** : Dossier 4 correspond au morceau ``3`` (éventuellement
        réduit par la méridienne) et est augmenté de 10 cm lorsque le dossier
        bas est présent.  La réduction de la méridienne se fait sur
        ``3`` lorsqu’il n’y a pas de scission, sinon sur ``3-bis``.  Le
        Dossier 4 bis (étiquette ``3-bis``) reflète la longueur restante
        du second morceau de la banquette droite et n’est jamais augmenté de 10 cm.

    Les résultats sont imprimés sur la sortie standard, chaque dossier
    sous la forme « L×10cm » où L est la longueur arrondie au centimètre
    près.

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise en ordre (par exemple
        ``['1', '2', '3']`` ou avec des suffixes ``'-bis'``).
    banquette_sizes : list of tuples
        Chaque tuple ``(L, P)`` correspond à la longueur et la profondeur
        de la mousse d’assise pour l’étiquette associée.
    angle_sizes : list of int
        Liste des longueurs des côtés de l’angle.  Pour U1F v1, une seule
        longueur est présente, correspondant au côté le plus long de
        l’angle.
    profondeur : int
        Profondeur de l’assise utilisée pour le Dossier 3.
    dossier_left, dossier_bas, dossier_right : bool
        Déterminent quel côté doit être imprimé (gauche, bas, droite).
    meridienne_side : str or None
        ``'g'`` si une méridienne est présente à gauche, ``'d'`` si une
        méridienne est présente à droite, ``None`` sinon.
    meridienne_len : int
        Longueur de la méridienne en centimètres.  Si zéro ou None,
        aucune réduction n’est appliquée.
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Ajuster selon la méridienne à gauche
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Ajuster selon la méridienne à droite
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)

    # Côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1
        if '1' in label_to_len:
            length1 = label_to_len['1']
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")
        # Dossier 1 angle
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            angle_len_adj = angle_len + (10 if dossier_bas else 0)
            print(f"  Dossier 1 angle = {angle_len_adj}x10cm")

    # Côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 2 angle (horizontal du coin)
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            print(f"  Dossier 2 angle = {angle_len}x10cm")
        # Dossier 2
        if '2' in label_to_len:
            length2 = label_to_len['2']
            print(f"  Dossier 2 = {length2}x10cm")
        # Dossier 2 bis
        if '2-bis' in label_to_len:
            length2bis = label_to_len['2-bis']
            print(f"  Dossier 2 bis = {length2bis}x10cm")
        # Dossier 3 : profondeur
        print(f"  Dossier 3 = {int(profondeur)}x10cm")

    # Côté droite
    if dossier_right:
        print("Dossiers Côté droite :")
        # Dossier 4
        # Dans la variante U1F v1, la longueur du Dossier 4 correspond au
        # morceau « 3 » (réduit de la méridienne le cas échéant) et est
        # augmentée de 10 cm lorsque le dossier bas est présent.
        if '3' in label_to_len:
            length4 = label_to_len['3'] + (10 if dossier_bas else 0)
            print(f"  Dossier 4 = {length4}x10cm")
        # Dossier 4 bis
        if '3-bis' in label_to_len:
            length4bis = label_to_len['3-bis']
            print(f"  Dossier 4 bis = {length4bis}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U1F v2
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U1F_v2(
    banquette_labels,
    banquette_sizes,
    angle_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour la variante U1F v2.

    La catégorisation des dossiers dépend exclusivement des indicateurs
    ``dossier_left``, ``dossier_bas`` et ``dossier_right``.  Les
    dimensions sont déterminées à partir des longueurs des mousses
    d’assise (labels « 1 », « 1-bis », « 2 », « 2-bis », « 3 », « 3-bis »),
    de la profondeur de l’assise et du côté d’angle.  Les règles sont :

      * **Côté gauche** : identique à la variante v1.  Dossier 1 et
        Dossier 1 bis utilisent respectivement les longueurs des morceaux
        « 1 » et « 1-bis » (avec soustraction de la méridienne si
        applicable), et un Dossier 1 angle de longueur égale à la
        dimension de l’angle, augmenté de 10 cm lorsque le dossier bas
        est présent.

      * **Côté bas** : Dossier 2 angle correspond au côté horizontal de
        l’angle (dimension d’angle).  Dossier 2 et Dossier 2 bis
        utilisent les longueurs des morceaux « 2 » et « 2-bis ».  Aucun
        dossier supplémentaire n’est imprimé sur cette branche.

      * **Côté droite** : Un Dossier 3 est imprimé avec une longueur
        égale à la profondeur de l’assise, augmentée de 10 cm lorsque le
        dossier bas est présent.  Dossier 4 est basé sur le morceau « 3 »
        (réduit de la méridienne si applicable) et **n’est pas** augmenté
        lorsque le dossier bas est présent.  Dossier 4 bis correspond au
        morceau « 3-bis » et voit sa longueur réduite de la méridienne si
        nécessaire, sans ajout supplémentaire.

    Les sorties suivent le format « L×10cm ».  La géométrie des
    polygones n’est pas utilisée pour déterminer les catégories.

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise dans l’ordre.
    banquette_sizes : list of tuples
        Liste des longueurs et profondeurs pour chaque étiquette.
    angle_sizes : list of int
        Longueurs des côtés de l’angle (un seul élément pour U1F).
    profondeur : int
        Profondeur de l’assise, utilisée pour le Dossier 3.
    dossier_left, dossier_bas, dossier_right : bool
        Flags pour afficher les dossiers de chaque côté.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'d'`` pour une méridienne à droite.
    meridienne_len : int
        Longueur de la méridienne en centimètres.  Si nul, aucune
        réduction n’est appliquée.
    """
    # Construire un dictionnaire label → longueur principale
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Ajuster les longueurs selon la méridienne à gauche
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Ajuster les longueurs selon la méridienne à droite
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        # La réduction s’applique au morceau 3-bis lorsqu’il existe, sinon au morceau 3
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)

    # Impression côté gauche (comme pour v1)
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1
        if '1' in label_to_len:
            length1 = label_to_len['1']
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")
        # Dossier 1 angle
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            angle_len_adj = angle_len + (10 if dossier_bas else 0)
            print(f"  Dossier 1 angle = {angle_len_adj}x10cm")

    # Impression côté bas (sans Dossier 3)
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 2 angle
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            print(f"  Dossier 2 angle = {angle_len}x10cm")
        # Dossier 2
        if '2' in label_to_len:
            length2 = label_to_len['2']
            print(f"  Dossier 2 = {length2}x10cm")
        # Dossier 2 bis
        if '2-bis' in label_to_len:
            length2bis = label_to_len['2-bis']
            print(f"  Dossier 2 bis = {length2bis}x10cm")

    # Impression côté droite
    if dossier_right:
        print("Dossiers Côté droite :")
        # Dossier 3 : retour vertical, basé sur la profondeur
        length3 = int(profondeur) + (10 if dossier_bas else 0)
        print(f"  Dossier 3 = {length3}x10cm")
        # Dossier 4 : premier morceau de la banquette droite
        # Pour U1F v2, la longueur du Dossier 4 est celle du morceau « 3 »
        # (éventuellement réduite par la méridienne).  Il n’y a pas
        # d’augmentation de +10 cm lorsque le dossier bas est présent.
        if '3' in label_to_len:
            length4 = label_to_len['3']
            print(f"  Dossier 4 = {length4}x10cm")
        # Dossier 4 bis : second morceau de la banquette droite (non augmenté)
        if '3-bis' in label_to_len:
            length4bis = label_to_len['3-bis']
            print(f"  Dossier 4 bis = {length4bis}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U1F v3
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U1F_v3(
    banquette_labels,
    banquette_sizes,
    angle_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour la variante U1F v3.

    La catégorisation ne dépend que des indicateurs ``dossier_left``,
    ``dossier_bas`` et ``dossier_right``.  Aucune reclassification
    géométrique n’est effectuée.  Les longueurs proviennent des
    mousses d’assise, de la profondeur de l’assise et de la dimension
    d’angle.

      * **Côté gauche** : Dossier 1 correspond au morceau « 1 »;
        si une méridienne est présente à gauche, la réduction est
        appliquée sur « 1-bis » lorsqu’il existe, sinon sur « 1 ».
        Dossier 1 bis correspond à « 1-bis » et est également réduit
        par la méridienne le cas échéant.  Aucun dossier d’angle n’est
        imprimé sur ce côté.

      * **Côté bas** : Dossier 2 est un retour vertical et sa longueur
        est égale à la profondeur de l’assise.  Dossiers 3 et 3 bis
        utilisent respectivement les morceaux « 2 » et « 2-bis ».  Un
        Dossier 1 angle est ajouté avec une longueur égale à la
        dimension d’angle (sans ajout de +10 cm).

      * **Côté droite** : Dossier 2 angle a pour longueur la dimension
        d’angle augmentée de 10 cm lorsque le dossier bas est présent.
        Dossier 4 utilise le morceau « 3 » (réduit de la méridienne si
        nécessaire) et **n’est pas** augmenté lorsque le dossier bas
        est présent.  Dossier 4 bis utilise le morceau « 3-bis »
        (réduit de la méridienne le cas échéant) sans ajout supplémentaire.

    Les longueurs sont affichées sous la forme « L×10cm ».

    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Ajuster les longueurs selon la méridienne à gauche
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Ajuster les longueurs selon la méridienne à droite
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)

    # Impression côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1
        if '1' in label_to_len:
            length1 = label_to_len['1']
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")

    # Impression côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 2 : retour vertical (profondeur)
        print(f"  Dossier 2 = {int(profondeur)}x10cm")
        # Dossier 3 et 3 bis (morceaux « 2 » et « 2-bis »)
        if '2' in label_to_len:
            length3 = label_to_len['2']
            print(f"  Dossier 3 = {length3}x10cm")
        if '2-bis' in label_to_len:
            length3bis = label_to_len['2-bis']
            print(f"  Dossier 3 bis = {length3bis}x10cm")
        # Dossier 1 angle : dimension d’angle
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            print(f"  Dossier 1 angle = {angle_len}x10cm")

    # Impression côté droite
    if dossier_right:
        print("Dossiers Côté droite :")
        # Dossier 2 angle : dimension angle augmentée de 10 cm si dossier bas
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            angle_len_adj = angle_len + (10 if dossier_bas else 0)
            print(f"  Dossier 2 angle = {angle_len_adj}x10cm")
        # Dossier 4 : premier morceau de la banquette droite
        # Dans U1F v3, le Dossier 4 correspond à la longueur du morceau « 3 »
        # (après éventuelle réduction de la méridienne).  Il n’y a pas
        # d’ajout de +10 cm en fonction de la présence du dossier bas.
        if '3' in label_to_len:
            length4 = label_to_len['3']
            print(f"  Dossier 4 = {length4}x10cm")
        # Dossier 4 bis : second morceau de la banquette droite (sans +10)
        if '3-bis' in label_to_len:
            length4bis = label_to_len['3-bis']
            print(f"  Dossier 4 bis = {length4bis}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour U1F v4
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_U1F_v4(
    banquette_labels,
    banquette_sizes,
    angle_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour la variante U1F v4.

    Cette variante suit des règles spécifiques :

      * **Côté gauche** : Dossier 1 et Dossier 1 bis sont calculés
        comme pour les variantes précédentes, en appliquant la
        réduction de la méridienne au morceau « 1-bis » lorsqu’il
        existe, sinon au morceau « 1 ».  Un Dossier 2 est ajouté, de
        longueur égale à la profondeur de l’assise augmentée de 10 cm
        lorsque le dossier bas est présent.

      * **Côté bas** : Dossier 3 et Dossier 3 bis utilisent les
        longueurs des morceaux « 2 » et « 2-bis ».  Un Dossier 1 angle
        est imprimé avec une longueur égale à la dimension de
        l’angle (sans ajout de +10 cm).  Aucun retour vertical n’est
        imprimé ici.

      * **Côté droite** : Dossier 2 angle est la dimension de
        l’angle augmentée de 10 cm si le dossier bas est présent.
        Dossier 4 est basé sur le morceau « 3 » (réduit de la
        méridienne lorsqu’il n’y a pas de morceau « 3-bis ») et **n’est pas
        augmenté** lorsque le dossier bas est présent.  Le
        Dossier 4 bis correspond au morceau « 3-bis » (réduit de la
        méridienne s’il existe) et n’est jamais augmenté de 10 cm.

    Les sorties sont formatées sous la forme « L×10cm ».
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Ajustement pour la méridienne à gauche
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Ajustement pour la méridienne à droite
    if meridienne_side == 'd' and meridienne_len and dossier_right:
        if '3-bis' in label_to_len:
            label_to_len['3-bis'] = max(label_to_len['3-bis'] - meridienne_len, 0)
        elif '3' in label_to_len:
            label_to_len['3'] = max(label_to_len['3'] - meridienne_len, 0)

    # Côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1
        if '1' in label_to_len:
            length1 = label_to_len['1']
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")
        # Dossier 2 : retour vertical (profondeur), +10 cm si dossier bas
        length2 = int(profondeur) + (10 if dossier_bas else 0)
        print(f"  Dossier 2 = {length2}x10cm")

    # Côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 3 et 3 bis (morceaux « 2 » et « 2-bis »)
        if '2' in label_to_len:
            length3 = label_to_len['2']
            print(f"  Dossier 3 = {length3}x10cm")
        if '2-bis' in label_to_len:
            length3bis = label_to_len['2-bis']
            print(f"  Dossier 3 bis = {length3bis}x10cm")
        # Dossier 1 angle : dimension de l’angle
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            print(f"  Dossier 1 angle = {angle_len}x10cm")

    # Côté droite
    if dossier_right:
        print("Dossiers Côté droite :")
        # Dossier 2 angle : dimension d’angle, +10 cm si dossier bas
        if angle_sizes:
            angle_len = int(angle_sizes[0])
            angle_len_adj = angle_len + (10 if dossier_bas else 0)
            print(f"  Dossier 2 angle = {angle_len_adj}x10cm")
        # Dossier 4 : morceau « 3 »
        # Pour U1F v4, la longueur du Dossier 4 est simplement celle du
        # morceau « 3 » (réduit de la méridienne si applicable).  Aucune
        # augmentation n’est appliquée lorsque le dossier bas est présent.
        if '3' in label_to_len:
            length4 = label_to_len['3']
            print(f"  Dossier 4 = {length4}x10cm")
        # Dossier 4 bis : morceau « 3-bis » sans +10
        if '3-bis' in label_to_len:
            length4bis = label_to_len['3-bis']
            print(f"  Dossier 4 bis = {length4bis}x10cm")

# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour la variante LF (L avec angle fromage)
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_LF(
    banquette_labels,
    banquette_sizes,
    angle_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour la variante LF (L avec angle fromage).

    Contrairement à la logique générique qui classe les dossiers selon leur
    orientation géométrique (verticale, horizontale ou angle), cette fonction
    classe les dossiers *uniquement* selon les côtés logique gauche et bas,
    déterminés par les booléens ``dossier_left`` et ``dossier_bas``.  Le
    côté droit n'existe pas dans cette variante, donc aucun dossier n'y
    est associé.

    Les règles appliquées sont les suivantes :

      * **Côté gauche** : Dossier 1 correspond au premier morceau
        d’assise (étiquette « 1 »).  Sa longueur est ajustée
        lorsque la méridienne est du côté gauche : si la méridienne est
        présente et qu’il n’y a pas de morceau « 1-bis », on retranche
        la longueur de la méridienne à ce morceau ; s’il existe un
        morceau « 1-bis », la réduction est appliquée sur ce
        second morceau, en conservant le morceau « 1 » plein.
        Le Dossier 1 bis est affiché séparément lorsque le morceau
        « 1-bis » existe ; sa longueur est réduite de la longueur de
        la méridienne si celle-ci est du côté gauche.  Enfin, si le
        côté bas est présent, un Dossier 1 angle est affiché et sa
        longueur est égale à la dimension de l’angle augmentée de
        10 cm.

      * **Côté bas** : Dossier 2 angle correspond au côté horizontal
        de l’angle et sa longueur est simplement la dimension de
        l’angle (sans ajout).  Dossier 2 et Dossier 2 bis
        correspondent aux morceaux d’assise avec étiquette « 2 » et
        « 2-bis » et n’utilisent pas la méridienne : ils sont
        affichés tels quels.  Aucune augmentation de 10 cm n’est
        appliquée sur ces morceaux.

    Les longueurs sont arrondies à l’entier pour l’affichage sous la
    forme « L×10cm ».

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise, par exemple ``['1', '2']`` ou
        ``['1', '1-bis', '2']``.
    banquette_sizes : list of tuples
        Paires ``(L, P)`` représentant la longueur et la profondeur de
        chaque morceau d’assise dans le même ordre que
        ``banquette_labels``.
    angle_sizes : list of int
        Liste contenant la longueur de l’unique côté de l’angle.
    profondeur : int
        Profondeur de l’assise, utilisée uniquement pour information.
    dossier_left : bool
        Indique si le côté gauche possède un dossier.
    dossier_bas : bool
        Indique si le côté bas possède un dossier.
    meridienne_side : str or None
        ``'g'`` si la méridienne est sur le côté gauche, ``None`` sinon.
    meridienne_len : int
        Longueur de la méridienne en centimètres.
    """
    # Construction du dictionnaire label → longueur (L) pour les morceaux d’assise
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Récupérer la dimension de l’angle.  Si non fournie, utiliser profondeur+20.
    if angle_sizes:
        angle_len = int(angle_sizes[0])
    else:
        angle_len = int(profondeur) + 20

    # Ajustement pour la méridienne à gauche sur le côté gauche uniquement
    if meridienne_side == 'g' and meridienne_len and dossier_left:
        if '1-bis' in label_to_len:
            label_to_len['1-bis'] = max(label_to_len['1-bis'] - meridienne_len, 0)
        elif '1' in label_to_len:
            label_to_len['1'] = max(label_to_len['1'] - meridienne_len, 0)

    # Côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1
        if '1' in label_to_len:
            length1 = label_to_len['1']
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            print(f"  Dossier 1 bis = {length1bis}x10cm")
        # Dossier 1 angle : uniquement si le côté bas est présent
        if dossier_bas:
            d1_angle_len = angle_len + 10
            print(f"  Dossier 1 angle = {d1_angle_len}x10cm")

    # Côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 2 angle : dimension de l’angle sans augmentation
        print(f"  Dossier 2 angle = {angle_len}x10cm")
        # Dossier 2 (et 2 bis) : longueurs des morceaux horizontaux
        if '2' in label_to_len:
            length2 = label_to_len['2']
            print(f"  Dossier 2 = {length2}x10cm")
        if '2-bis' in label_to_len:
            length2bis = label_to_len['2-bis']
            print(f"  Dossier 2 bis = {length2bis}x10cm")

# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour les canapés en L (variants LNF)
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_LNF_v1(
    banquette_labels,
    banquette_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour les canapés en L.

    Cette logique remplace complètement les heuristiques basées sur la
    géométrie.  Les dossiers sont regroupés uniquement selon les côtés
    déclarés par les booléens ``dossier_left`` et ``dossier_bas``.  La
    présence d'une méridienne à gauche ou en bas peut réduire la longueur
    du morceau concerné.  Aucune reclassification des dossiers selon
    l'orientation géométrique n'est effectuée.

    Règles appliquées :

      * **Côté gauche** : le Dossier 1 est basé sur la longueur du
        morceau d’assise étiqueté « 1 ».  Si une méridienne est
        positionnée à gauche (``meridienne_side`` = « g ») et qu’il
        n’existe pas de scission « 1-bis », la longueur de la méridienne
        est soustraite.  Lorsque le côté bas possède un dossier, 10 cm
        supplémentaires sont ajoutés à cette longueur.  Le Dossier 1 bis
        reflète la longueur du morceau « 1-bis » éventuel et est réduit
        de la longueur de la méridienne lorsqu’elle est à gauche.

      * **Côté bas** : le Dossier 2 utilise la longueur du morceau
        d’assise « 2 ».  Lorsqu’une méridienne est au bas (``meridienne_side``
        = « b ») et qu’il n’y a pas de scission « 2-bis », la longueur
        de la méridienne est retirée.  Le Dossier 2 bis représente le
        morceau « 2-bis » éventuel et est réduit de la longueur de la
        méridienne lorsqu’elle est en bas.  Enfin, le Dossier 3 est un
        retour vertical de longueur égale à la profondeur de l’assise.

    Les valeurs affichées correspondent au nombre de longueurs de mousse
    (multiplié par 10 cm).  Les longueurs négatives résultant d’une
    soustraction sont ramenées à zéro.

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (ex. « 1 », « 1-bis », « 2 », « 2-bis »).
    banquette_sizes : list of tuple
        Paires ``(L, P)`` représentant la longueur et la profondeur des
        morceaux d’assise dans le même ordre que ``banquette_labels``.
    profondeur : int
        Profondeur de l’assise (en cm).
    dossier_left : bool
        Si vrai, le côté gauche comporte un dossier.
    dossier_bas : bool
        Si vrai, le côté bas comporte un dossier.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'b'`` pour une méridienne
        en bas, ``None`` s’il n’y a pas de méridienne.
    meridienne_len : int
        Longueur de la méridienne en centimètres.
    """
    # Construire un dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1 : longueur du morceau « 1 », ajustée selon la méridienne
        if '1' in label_to_len:
            length1 = label_to_len['1']
            # Méridienne à gauche et pas de scission « 1-bis » → on réduit « 1  »
            if meridienne_side == 'g' and meridienne_len:
                if '1-bis' not in label_to_len:
                    length1 = max(length1 - meridienne_len, 0)
            # Ajout de +10 cm si le dossier bas est présent
            length1_display = length1 + (10 if dossier_bas else 0)
            print(f"  Dossier 1 = {length1_display}x10cm")
        # Dossier 1 bis : morceau « 1-bis » réduit de la méridienne si applicable
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            if meridienne_side == 'g' and meridienne_len:
                length1bis = max(length1bis - meridienne_len, 0)
            print(f"  Dossier 1 bis = {length1bis}x10cm")

    # Côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 2 : longueur du morceau « 2 » avec éventuelle réduction
        if '2' in label_to_len:
            length2 = label_to_len['2']
            if meridienne_side == 'b' and meridienne_len:
                # Réduction uniquement s'il n'y a pas de scission « 2-bis  »
                if '2-bis' not in label_to_len:
                    length2 = max(length2 - meridienne_len, 0)
            print(f"  Dossier 2 = {length2}x10cm")
        # Dossier 2 bis : morceau « 2-bis » réduit de la méridienne si applicable
        if '2-bis' in label_to_len:
            length2bis = label_to_len['2-bis']
            if meridienne_side == 'b' and meridienne_len:
                length2bis = max(length2bis - meridienne_len, 0)
            print(f"  Dossier 2 bis = {length2bis}x10cm")
        # Dossier 3 : retour vertical = profondeur
        print(f"  Dossier 3 = {int(profondeur)}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour les canapés en L variante v2
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_LNF_v2(
    banquette_labels,
    banquette_sizes,
    profondeur,
    dossier_left,
    dossier_bas,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour les canapés en L, variante v2.

    Contrairement à la variante v1, la longueur du Dossier 1 n’est
    jamais augmentée de 10 cm lorsque le dossier bas est présent.  Si
    une méridienne gauche est en place et qu’il n’existe pas de
    scission « 1-bis », la réduction de la longueur liée à la
    méridienne ne s’applique que lorsque le dossier bas est absent.
    Lorsque la banquette « 1 » est scindée (« 1-bis » présent), la
    réduction éventuelle est appliquée uniquement sur le morceau
    « 1-bis ».

    Le retour vertical (Dossier 2) est imprimé sur le côté gauche et
    prend la valeur de la profondeur (augmentée de 10 cm lorsque le
    côté bas possède un dossier).  Sur le côté bas, les dossiers 3 et
    3 bis reflètent la longueur des morceaux d’assise « 2 » et
    « 2-bis » avec une éventuelle réduction appliquée en cas de
    méridienne basse.  Aucun reclassement géométrique n’est effectué :
    seules les étiquettes « 1 », « 1-bis », « 2 », « 2-bis » définissent
    les longueurs à imprimer.

    Parameters
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (ex. « 1 », « 1-bis », « 2 », « 2-bis »).
    banquette_sizes : list of tuple
        Paires ``(L, P)`` représentant la longueur et la profondeur des
        morceaux d’assise dans le même ordre que ``banquette_labels``.
    profondeur : int
        Profondeur de l’assise (en cm).
    dossier_left : bool
        Si vrai, le côté gauche comporte un dossier.
    dossier_bas : bool
        Si vrai, le côté bas comporte un dossier.
    meridienne_side : str or None
        ``'g'`` pour une méridienne à gauche, ``'b'`` pour une méridienne
        en bas, ``None`` s’il n’y a pas de méridienne.
    meridienne_len : int
        Longueur de la méridienne en centimètres.
    """
    # Dictionnaire label → longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Côté gauche
    if dossier_left:
        print("Dossiers Côté gauche :")
        # Dossier 1 : longueur du morceau « 1 » ajustée selon la méridienne à gauche.
        # Dans la variante v2, la réduction pour la méridienne gauche ne
        # s'applique que s'il n'existe pas de scission « 1-bis » ET que le
        # dossier bas est absent.  Autrement, on conserve la longueur
        # originale.
        if '1' in label_to_len:
            length1 = label_to_len['1']
            if meridienne_side == 'g' and meridienne_len:
                # Réduction uniquement s'il n'y a pas de 1-bis et si le dossier bas est absent
                if '1-bis' not in label_to_len and not dossier_bas:
                    length1 = max(length1 - meridienne_len, 0)
            print(f"  Dossier 1 = {length1}x10cm")
        # Dossier 1 bis : morceau « 1-bis » réduit de la méridienne à gauche
        if '1-bis' in label_to_len:
            length1bis = label_to_len['1-bis']
            if meridienne_side == 'g' and meridienne_len:
                length1bis = max(length1bis - meridienne_len, 0)
            print(f"  Dossier 1 bis = {length1bis}x10cm")
        # Dossier 2 : retour vertical = profondeur (+10 cm si dossier bas)
        length2 = int(profondeur) + (10 if dossier_bas else 0)
        print(f"  Dossier 2 = {length2}x10cm")

    # Côté bas
    if dossier_bas:
        print("Dossiers Côté bas :")
        # Dossier 3 : longueur du morceau « 2 » avec éventuelle réduction à la méridienne basse
        if '2' in label_to_len:
            length3 = label_to_len['2']
            if meridienne_side == 'b' and meridienne_len:
                # Réduction uniquement s'il n'y a pas de scission « 2-bis  »
                if '2-bis' not in label_to_len:
                    length3 = max(length3 - meridienne_len, 0)
            print(f"  Dossier 3 = {length3}x10cm")
        # Dossier 3 bis : morceau « 2-bis » réduit de la méridienne basse
        if '2-bis' in label_to_len:
            length3bis = label_to_len['2-bis']
            if meridienne_side == 'b' and meridienne_len:
                length3bis = max(length3bis - meridienne_len, 0)
            print(f"  Dossier 3 bis = {length3bis}x10cm")


# -------------------------------------------------------------------------
# Affichage des dimensions des dossiers pour les canapés simples S1
# -------------------------------------------------------------------------
def _print_dossiers_dimensions_simple_S1(
    banquette_labels,
    banquette_sizes,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Affiche les dimensions des dossiers pour un canapé simple (S1).

    Les dimensions sont calculées à partir des longueurs de mousse
    correspondant à chaque tronçon d’assise.  La règle appliquée est la
    suivante :

      * Le dossier 1 prend la longueur de la mousse 1.  Lorsqu’une
        méridienne est présente, on retranche systématiquement la
        longueur de la méridienne gauche.  La méridienne droite,
        en revanche, ne réduit le dossier 1 que s’il n’existe pas de
        tronçon « 1‑bis  ».

          - Méridienne gauche : la longueur de la méridienne est
            toujours retranchée du dossier 1, qu’il y ait ou non une
            scission de l’assise.

          - Méridienne droite : si le canapé n’est pas scindé, le
            dossier 1 est réduit de la longueur de la méridienne.  Si
            un tronçon « 1‑bis » existe, la méridienne droite ne réduit
            pas le dossier 1.

      * Si un tronçon « 1‑bis » est présent (banquette scindée), le
        dossier 1 bis prend la longueur de la mousse « 1‑bis ».  Une
        méridienne droite réduit cette longueur ; une méridienne gauche
        n’a aucun impact sur le dossier 1 bis.

    Les longueurs sont exprimées en dizaines de centimètres : un
    dossier de longueur L cm est affiché comme « L×10 cm ».  Les valeurs
    négatives sont ramenées à zéro.

    Paramètres
    ----------
    banquette_labels : list of str
        Étiquettes des morceaux d’assise (par exemple « 1 », « 1-bis »).
    banquette_sizes : list of tuple
        Paires ``(L, P)`` représentant la longueur et la profondeur des
        banquettes dans le même ordre que ``banquette_labels``.
    meridienne_side : str or None
        ``'g'`` pour une méridienne gauche, ``'d'`` pour une méridienne
        droite, ``None`` s’il n’y a pas de méridienne.
    meridienne_len : int
        Longueur de la méridienne en centimètres.
    """
    # Construire un dictionnaire label -> longueur principale (L)
    label_to_len = {lab: int(L) for lab, (L, _P) in zip(banquette_labels, banquette_sizes)}

    # Calcul des longueurs initiales
    length1 = label_to_len.get('1')
    length1bis = label_to_len.get('1-bis')

    # Ajustements selon la méridienne
    if meridienne_side == 'g' and meridienne_len:
        # La méridienne gauche réduit toujours la longueur du dossier 1
        if length1 is not None:
            length1 = max(length1 - meridienne_len, 0)

    if meridienne_side == 'd' and meridienne_len:
        if '1-bis' not in label_to_len:
            # Pas de scission : la méridienne droite réduit « 1  »
            if length1 is not None:
                length1 = max(length1 - meridienne_len, 0)
        else:
            # Avec scission : la méridienne droite réduit « 1-bis  »
            if length1bis is not None:
                length1bis = max(length1bis - meridienne_len, 0)

    # Affichage des dossiers
    if length1 is not None:
        print(f"  Dossier 1 = {length1}x10cm")
    if length1bis is not None:
        print(f"  Dossier 1 bis = {length1bis}x10cm")

# -------------------------------------------------------------------------
# Calcul des dimensions des accoudoirs et impression (toutes variantes)
# -------------------------------------------------------------------------
def _compute_accoudoirs_dimensions(polys):
    """
    Calcule les longueurs et épaisseurs des accoudoirs et les classe
    selon le côté gauche, bas ou droite.

    Les accoudoirs sont fournis sous forme de listes de polygones
    (rectangles) en coordonnées « cm ».  Pour déterminer le côté, on
    compare le centre du polygone à celui du canapé entier.  Un
    accoudoir vertical est affecté au côté gauche ou droit selon que
    son centre est situé à gauche ou à droite du centre global.  Un
    accoudoir horizontal est toujours affecté au côté bas.

    Parameters
    ----------
    polys : dict
        Dictionnaire contenant les listes de polygones pour les
        différents éléments du canapé, notamment ``accoudoirs``.

    Returns
    -------
    list of tuple
        Liste de tuples ``(côté, longueur, épaisseur)`` où ``côté`` est
        l'une des valeurs ``'gauche'``, ``'bas'`` ou ``'droite'``,
        ``longueur`` est la grande dimension du polygone (arrondie),
        et ``épaisseur`` est la petite dimension.
    """
    arms = polys.get("accoudoirs") or []
    if not arms:
        return []
    # Construire une boîte englobante du canapé pour définir le centre
    xs_all = []
    ys_all = []
    for key in ("banquettes", "angle", "angles", "dossiers", "accoudoirs"):
        for poly in polys.get(key, []):
            xs_all.extend([pt[0] for pt in poly])
            ys_all.extend([pt[1] for pt in poly])
    if not xs_all or not ys_all:
        return []
    min_x, max_x = min(xs_all), max(xs_all)
    min_y, max_y = min(ys_all), max(ys_all)
    cx_center = 0.5 * (min_x + max_x)
    cy_center = 0.5 * (min_y + max_y)
    results = []
    for poly in arms:
        if not poly:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        width = maxx - minx
        height = maxy - miny
        # Longueur = plus grande dimension; épaisseur = plus petite.
        length = int(round(max(width, height)))
        thickness = int(round(min(width, height)))
        # Centre de l'accoudoir
        cx = 0.5 * (minx + maxx)
        cy = 0.5 * (miny + maxy)
        # Orientation : vertical ou horizontal
        if height > width:
            # Vertical : classer à gauche/droite selon x
            side = "gauche" if cx < cx_center else "droite"
        else:
            # Horizontal : distinguer bas ou côtés latéraux.  Lorsque
            # l'accoudoir est situé sous le centre vertical (cy <= cy_center),
            # il est considéré comme un accoudoir du bas.  Sinon, il est
            # attaché à une branche latérale et on choisit gauche/droite
            # selon sa position horizontale.
            if cy <= cy_center:
                side = "bas"
            else:
                side = "gauche" if cx < cx_center else "droite"
        results.append((side, length, thickness))
    return results

def _print_accoudoirs_dimensions(polys):
    """
    Imprime les dimensions des accoudoirs sur la console en suivant
    l'ordre gauche, bas, droite.  Les accoudoirs sont omis s'il n'y en a
    pas.

    Parameters
    ----------
    polys : dict
        Dictionnaire de polygones avec la clé ``accoudoirs``.
    """
    dims = _compute_accoudoirs_dimensions(polys)
    if not dims:
        return
    # Tri par ordre logique des côtés
    order = {"gauche": 0, "bas": 1, "droite": 2}
    dims_sorted = sorted(dims, key=lambda d: order.get(d[0], 3))
    print("Accoudoirs :")
    for side, length, thickness in dims_sorted:
        print(f"  Accoudoir côté {side} = {length}x{thickness}cm")


# -*- coding: utf-8 -*-
# canape_complet_v6_palette_legende_U.py
# Base validée + ajouts :
#   - Choix des couleurs par noms FR (gris, beige, gris foncé/foncée, taupe, crème, etc.) ou #hex
#   - Préréglage demandé : accoudoirs=gris ; dossiers=gris (plus clair) ;
#                          assises=gris très clair (presque blanc) ; coussins=taupe
#   - Dossiers automatiquement un ton plus clair que accoudoirs si non précisé
#   - Légende "U" déplacée en haut-centré (hors canapé) ; autres : haut-droite
#   - Légende affiche la couleur choisie ("Dossier (gris clair)", etc.)
#   - Correctifs nommage 'coussins_count' -> 'cushions_count'

import math, unicodedata
# Import conditionnel de Matplotlib pour supporter l'exécution sans cette
# dépendance. Si Matplotlib n'est pas disponible, les variables ``plt`` et
# ``mpatches`` sont mises à ``None`` et l'on bascule plus bas sur le module
# Turtle natif pour l'affichage.
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    plt = None
    mpatches = None

# --- Adaptateur léger "turtle" -> matplotlib ---------------------------------
# On crée un pseudo-module "turtle" compatible avec ce qu'utilise ce script :
#   - turtle.Screen().setup(...), .title(...), .tracer(...)
#   - turtle.Turtle(visible=False) avec : speed, pensize, pencolor, fillcolor,
#     up/down, goto, setheading, left, forward, begin_fill, end_fill,
#     circle, write, hideturtle
#   - turtle.done() pour afficher la figure.

_current_screen = None

class _MplScreen:
    def __init__(self):
        global _current_screen
        self.fig, self.ax = plt.subplots()
        self.ax.set_aspect("equal", adjustable="box")
        self.ax.axis("off")
        _current_screen = self

    def setup(self, w, h):
        # w, h sont en pixels dans le code d'origine. On les convertit
        # grossièrement en pouces pour matplotlib (100 px ~ 1").
        try:
            self.fig.set_size_inches(w / 100.0, h / 100.0, forward=True)
        except Exception:
            pass

    def title(self, txt):
        self.fig.suptitle(txt)

    def tracer(self, flag):
        # Dans turtle, tracer(False/True) pilote l'animation progressive.
        # Ici on dessine tout d'un coup, on ignore donc ce paramètre.
        pass


class _MplTurtle:
    def __init__(self, visible=True):
        global _current_screen
        if _current_screen is None:
            _MplScreen()
        self.screen = _current_screen
        self.ax = self.screen.ax
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0   # degrés, 0 = vers la droite
        self.is_down = False
        self.pen_color = "black"
        self.pen_size = 1.0
        self.fill_color = None
        self.is_filling = False
        self._fill_path = []

    # configuration "turtle"
    def speed(self, *args, **kwargs):
        # ignoré en mode matplotlib
        pass

    def pensize(self, w):
        self.pen_size = w

    def pencolor(self, c):
        self.pen_color = c

    def fillcolor(self, c):
        self.fill_color = c

    # déplacements / stylo
    def up(self):
        self.is_down = False
    penup = up

    def down(self):
        self.is_down = True
    pendown = down

    def setheading(self, angle):
        self.heading = float(angle)

    def left(self, angle):
        self.heading += float(angle)

    def forward(self, dist):
        ang = math.radians(self.heading)
        nx = self.x + dist * math.cos(ang)
        ny = self.y + dist * math.sin(ang)
        self.goto(nx, ny)
    fd = forward

    def goto(self, x, y):
        x = float(x); y = float(y)
        if self.is_down:
            if self.is_filling:
                # On accumule les points, le remplissage se fera dans end_fill()
                self._fill_path.append((x, y))
            else:
                # On trace immédiatement un segment
                self.ax.plot([self.x, x], [self.y, y],
                             linewidth=self.pen_size, color=self.pen_color)
        self.x, self.y = x, y

    # remplissage
    def begin_fill(self):
        self.is_filling = True
        self._fill_path = [(self.x, self.y)]

    def end_fill(self):
        if self.is_filling and len(self._fill_path) >= 3:
            poly = mpatches.Polygon(self._fill_path, closed=True,
                                    edgecolor=self.pen_color,
                                    facecolor=self.fill_color or "none",
                                    linewidth=self.pen_size)
            self.ax.add_patch(poly)
        self.is_filling = False
        self._fill_path = []

    # arcs et cercles (approximation par segments)
    def circle(self, radius, extent=360):
        # On approxime l'arc avec de petits segments
        steps = max(4, int(abs(extent) / 5.0))
        step_angle = float(extent) / steps
        # longueur approximative de chaque petit segment
        step_len = 2 * math.pi * abs(radius) * abs(step_angle) / 360.0
        for _ in range(steps):
            self.left(step_angle)
            self.forward(step_len)

    # texte
    def write(self, text, align="left", font=None):
        ha = {"left": "left", "center": "center", "right": "right"}.get(align, "left")
        kwargs = {}
        if font:
            if len(font) >= 2:
                kwargs["fontfamily"] = font[0]
                kwargs["fontsize"] = font[1]
            if len(font) >= 3 and str(font[2]).lower() == "bold":
                kwargs["fontweight"] = "bold"
        self.ax.text(self.x, self.y, str(text),
                     ha=ha, va="center", **kwargs)

    def hideturtle(self):
        # rien à cacher en matplotlib
        pass


class _TurtleModule:
    Screen = _MplScreen
    Turtle = _MplTurtle

    @staticmethod
    def done():
        # Ajuste les limites automatiquement autour de ce qui a été dessiné
        plt.axis("equal")
        plt.tight_layout()
        plt.show()


# On expose un objet "turtle" qui remplace le module turtle standard
turtle = _TurtleModule()

# ---------------------------------------------------------------------------
# Bascule sur le module ``turtle`` natif si Matplotlib n'est pas disponible
# ou si l'on souhaite exécuter le script dans un environnement comme Thonny
# sans installer de dépendances supplémentaires. Cette réaffectation se
# contente d'importer le module standard et d'écraser la variable ``turtle``
# utilisée partout dans le code. Le reste du script n'est pas modifié.
try:
    import turtle as _real_turtle
    # si Matplotlib n'est pas importé (plt est None), ou tout simplement
    # pour forcer l'usage de la fenêtre Turtle, on remplace l'objet
    # précédemment défini par l'adaptateur Matplotlib.
    if plt is None:
        turtle = _real_turtle
except Exception:
    # en cas d'absence de Tkinter ou d'un autre problème, on conserve
    # l'adaptateur matplotlib
    pass


# =========================
# Réglages / constantes
# =========================
WIN_W, WIN_H       = 900, 700
PAD_PX             = 60
ZOOM               = 0.85
LINE_WIDTH         = 2

# ========= PALETTE / THÈME =========
# Couleurs par défaut, selon la demande :
# - accoudoirs = gris (moyen)
# - dossiers = gris (un ton plus clair)
# - assises/banquettes = gris très clair (presque blanc)
# - coussins = taupe
# NB : Ces valeurs seront éventuellement écrasées à chaque render_* via _resolve_and_apply_colors()
COLOR_ASSISE       = "#f6f6f6"  # gris très clair / presque blanc
COLOR_ACC          = "#8f8f8f"  # gris
COLOR_DOSSIER      = "#b8b8b8"  # gris plus clair que accoudoirs
COLOR_CUSHION      = "#8B7E74"  # taupe
COLOR_CONTOUR      = "black"

# (Conservés mais non utilisés car quadrillage/repères supprimés)
GRID_MINOR_STEP    = 10
GRID_MAJOR_STEP    = 50
COLOR_GRID_MINOR   = "#f0f0f0"
COLOR_GRID_MAJOR   = "#dcdcdc"
AXIS_LABEL_STEP    = 50
AXIS_LABEL_MAX     = 800

DEPTH_STD          = 70
ACCOUDOIR_THICK    = 15
DOSSIER_THICK      = 10
CUSHION_DEPTH      = 15

# *** Seuil strict de scission ***
MAX_BANQUETTE      = 250
SPLIT_THRESHOLD    = 250  # scission dès que longueur > 250 (aucune tolérance)

# --- Coins arrondis coussins ---
CUSHION_ROUND_R_CM = 3.0  # rayon ~3 cm, léger

# --- Traversins (bolsters) ---
TRAVERSIN_LEN   = 70     # longueur selon la profondeur
# La largeur (épaisseur) des traversins passe de 30 cm à 20 cm.
# Le retrait appliqué sur la ligne de coussins doit donc être réduit.
TRAVERSIN_THK   = 20     # retrait sur la ligne de coussins (20 cm)
COLOR_TRAVERSIN = "#e0d9c7"

def _segment_x_limits(pts, a_key, b_key):
    """
    Retourne (x_min, x_max, y) pour le segment horizontal défini par deux
    points partageant le même y (ex.: By–By2 ou By3–By4).
    """
    ax, ay = pts[a_key]
    bx, by = pts[b_key]
    # Par sécurité on ne s'appuie pas sur un éventuel By_ / By4_ (méridienne)
    # → l'appelant fournit explicitement By/By2/By3/By4.
    x0 = min(ax, bx)
    x1 = max(ax, bx)
    y  = ay  # ay == by par construction
    return x0, x1, y

def _clamp_to_segment(x0, length, seg_min, seg_max, align="start"):
    """
    Calcule [X0, X1] pour une brique de 'length' posée DANS [seg_min, seg_max].
    - align='start'  → coller au début du segment (gauche)
    - align='end'    → coller à la fin   du segment (droite)
    """
    length = max(0.0, float(length))
    if align == "start":
        X0 = max(seg_min, min(x0, seg_max))
        X1 = min(seg_max, X0 + length)
        # Si la longueur excède le segment, on se borne au segment complet
        if X1 - X0 < length:
            X0 = seg_min
            X1 = min(seg_max, seg_min + length)
    else:  # align == "end"
        X1 = min(seg_max, max(x0, seg_min))
        X0 = max(seg_min, X1 - length)
        if X1 - X0 < length:
            X1 = seg_max
            X0 = max(seg_min, seg_max - length)
    return X0, X1

# --- Polices / légende / titres (lisibilité accrue) ---
# Réduction légère des tailles de police pour une meilleure lisibilité
FONT_LABEL      = ("Arial", 10, "bold")   # libellés banquettes/dossiers/accoudoirs
FONT_CUSHION    = ("Arial", 9,  "bold")   # tailles des coussins + "70x20"
FONT_DIM        = ("Arial", 10, "bold")   # flèches d’encombrement
FONT_LEGEND     = ("Arial", 10, "normal") # texte de légende
FONT_TITLE      = ("Arial", 12, "bold")   # titre "Canapé en U …"
# Slightly smaller font for backrest thickness labels
FONT_DOSSIER    = ("Arial", 8, "bold")
LEGEND_BOX_PX   = 14
LEGEND_GAP_PX   = 6
TITLE_MARGIN_PX = 28  # marge sous le bord haut du dessin

# --- Sécurité d'affichage pour la légende ---
LEGEND_SAFE_PX = 16   # distance minimale entre la légende et le schéma (px)
LEGEND_EDGE_PX = 10   # marge minimale par rapport aux bords de fenêtre (px)

# =============================================================================
# ================     OUTILS PALETTE / COULEURS (NOUVEAU)     ================
# =============================================================================

# Palette de base (nuanciers simples)
_BASE_COLORS = {
    "gris":   "#9e9e9e",
    "beige":  "#d8c4a8",
    "taupe":  "#8B7E74",
    "crème":  "#f4f1e9",
    "creme":  "#f4f1e9",
    "blanc":  "#ffffff",
    "noir":   "#111111",
    "sable":  "#e6d8b8",
    "anthracite": "#4b4b4b",
}

# Helpers accents/normalisation
def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = _strip_accents(s)
    return ' '.join(s.split())

def _clamp(x, lo=0, hi=255):
    return int(max(lo, min(hi, round(x))))

def _hex_to_rgb(h):
    h = h.strip()
    if h.startswith("#"):
        h = h[1:]
    if len(h) == 3:
        h = ''.join([c*2 for c in h])
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))

def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)

def _lighten(hexcol, factor):
    """factor in [0,1] vers blanc; 0 = identique; 1 = blanc complet."""
    r,g,b = _hex_to_rgb(hexcol)
    r = _clamp(r + (255-r)*factor)
    g = _clamp(g + (255-g)*factor)
    b = _clamp(b + (255-b)*factor)
    return _rgb_to_hex((r,g,b))

def _darken(hexcol, factor):
    """factor in [0,1] vers noir; 0 = identique; 1 = noir complet."""
    r,g,b = _hex_to_rgb(hexcol)
    r = _clamp(r*(1-factor))
    g = _clamp(g*(1-factor))
    b = _clamp(b*(1-factor))
    return _rgb_to_hex((r,g,b))

def _apply_shade(hexcol, tokens):
    """
    tokens: contient éventuellement 'clair', 'tres clair', 'fonce', 'tres fonce', 'presque blanc'
    """
    t = ' '.join(tokens)
    t_norm = _norm(t)
    if "presque blanc" in t_norm:
        return _lighten(hexcol, 0.75)
    if "tres clair" in t_norm:
        return _lighten(hexcol, 0.40)
    if "clair" in t_norm:
        return _lighten(hexcol, 0.22)
    if "tres fonce" in t_norm:
        return _darken(hexcol, 0.40)
    if "fonce" in t_norm or "foncee" in t_norm:
        return _darken(hexcol, 0.22)
    return hexcol

def _pretty_shade(tokens):
    t = _norm(' '.join(tokens))
    t = t.replace("tres", "très")
    t = t.replace("fonce", "foncé")
    return t

def _parse_color_value(val):
    """
    Convertit un nom FR (évent. qualifié) ou un #hex en (#hex, nom jolis mots ou None)
    Ex : "gris foncé" -> (#..., "gris foncé")
         "#c0ffee"    -> ("#c0ffee", None)
    """
    if val is None:
        return None, None
    s_raw = str(val).strip()
    s = _norm(s_raw)

    # cas hex
    if s.startswith("#") or all(c in "0123456789abcdef" for c in s.replace("#","")) and len(s.replace("#","")) in (3,6):
        try:
            _ = _hex_to_rgb(s)
            if not s.startswith("#"): s = "#" + s
            return s, None
        except Exception:
            pass

    # cherche base connue
    tokens = s.split()
    if not tokens:
        return None, None

    # base candidates (un ou deux mots, ex "gris", "blanc", "beige", "taupe")
    base = tokens[0]
    base_hex = _BASE_COLORS.get(base)
    if base_hex is None and len(tokens)>=2:
        # ex: "gris clair" = base "gris" + shade "clair"
        base_hex = _BASE_COLORS.get(tokens[0])
    if base_hex is None:
        # fallback : gris
        base_hex = _BASE_COLORS["gris"]; base = "gris"

    shade = tokens[1:] if len(tokens)>1 else []
    hexcol = _apply_shade(base_hex, shade)
    pretty = base
    if shade:
        pretty += " " + _pretty_shade(shade)
    return hexcol, pretty

def _parse_couleurs_argument(couleurs):
    """
    Accepte dict, ou string "clé:val; clé:val".
    Normalise les clés en {'accoudoirs','dossiers','assise','coussins'}
    """
    if couleurs is None:
        return {}

    if isinstance(couleurs, dict):
        raw = { _norm(k): str(v) for k,v in couleurs.items() }
    else:
        raw = {}
        for part in str(couleurs).split(";"):
            if ":" in part:
                k,v = part.split(":",1)
                raw[_norm(k)] = v.strip()

    keymap = {
        "accoudoir":"accoudoirs", "accoudoirs":"accoudoirs",
        "dossier":"dossiers", "dossiers":"dossiers",
        "assise":"assise", "assises":"assise", "banquette":"assise", "banquettes":"assise",
        "coussin":"coussins", "coussins":"coussins"
    }
    res={}
    for k,v in raw.items():
        kn = keymap.get(k, k)
        if kn in ("accoudoirs","dossiers","assise","coussins"):
            res[kn] = v
    return res

def _resolve_and_apply_colors(couleurs):
    """
    Résout la palette utilisateur puis applique aux variables globales:
      COLOR_ASSISE, COLOR_ACC, COLOR_DOSSIER, COLOR_CUSHION
    Retourne une liste d'items pour la légende: [(libellé, hex, nom)]
    Règle : si dossiers non spécifié mais accoudoirs oui => dossiers = accoudoirs éclaircis.
    """
    global COLOR_ASSISE, COLOR_ACC, COLOR_DOSSIER, COLOR_CUSHION

    # base par défaut (demande client)
    default = {
        "accoudoirs": "gris",
        "dossiers":   None,  # sera éclairci à partir des accoudoirs si None
        "assise":     "gris très clair presque blanc",
        "coussins":   "taupe",
    }
    user = _parse_couleurs_argument(couleurs)
    spec = {**default, **user}

    # accoudoirs
    acc_hex, acc_name = _parse_color_value(spec["accoudoirs"])
    # dossiers
    if spec["dossiers"] is None:
        # auto : un ton plus clair que accoudoirs
        dos_hex = _lighten(acc_hex, 0.20)
        dos_name = (acc_name+" clair") if acc_name else "gris clair"
    else:
        dos_hex, dos_name = _parse_color_value(spec["dossiers"])
    # assise
    ass_hex, ass_name = _parse_color_value(spec["assise"])
    # coussins
    cush_hex, cush_name = _parse_color_value(spec["coussins"])

    # applique globals
    COLOR_ACC     = acc_hex
    COLOR_DOSSIER = dos_hex
    COLOR_ASSISE  = ass_hex
    COLOR_CUSHION = cush_hex

    # Items de légende (texte + nom de couleur si dispo)
    items = [
        ("Dossier",   COLOR_DOSSIER, dos_name),
        ("Accoudoir", COLOR_ACC,     acc_name),
        ("Coussins",  COLOR_CUSHION, cush_name),
        ("Assise",    COLOR_ASSISE,  ass_name),
    ]
    return items

# =========================
# Transform cm → px (isométrique & centré)
# =========================
class WorldToScreen:
    def __init__(self, tx_cm, ty_cm, win_w=WIN_W, win_h=WIN_H, pad_px=PAD_PX, zoom=ZOOM):
        sx = (win_w - 2*pad_px) / float(tx_cm or 1)
        sy = (win_h - 2*pad_px) / float(ty_cm or 1)
        self.scale = min(sx, sy) * zoom
        used_w = tx_cm * self.scale
        used_h = ty_cm * self.scale
        self.left_px   = -used_w / 2.0
        self.bottom_px = -used_h / 2.0
    def pt(self, x_cm, y_cm):
        return (self.left_px + x_cm*self.scale, self.bottom_px + y_cm*self.scale)

# =========================
# Outils dessin
# =========================
def pen_up_to(t, x, y):
    t.up(); t.goto(x, y)

def _is_axis_aligned_rect(pts):
    """Détecte un rectangle axis‑aligné fermé (le dernier point répète le premier)."""
    if not pts or len(pts) < 4:
        return False
    body = pts[:-1] if pts[0] == pts[-1] else pts
    if len(body) != 4:
        return False
    xs = {round(x, 6) for x, _ in body}
    ys = {round(y, 6) for _, y in body}
    return len(xs) == 2 and len(ys) == 2

def draw_rounded_rect_cm(t, tr, x0, y0, x1, y1, r_cm=CUSHION_ROUND_R_CM,
                         fill=None, outline=COLOR_CONTOUR, width=LINE_WIDTH):
    # normalise
    if x0 > x1: x0, x1 = x1, x0
    if y0 > y1: y0, y1 = y1, y0
    rx = max(0.0, min(r_cm, (x1-x0)/2.0, (y1-y0)/2.0))
    wpx = (x1 - x0) * tr.scale
    hpx = (y1 - y0) * tr.scale
    rpx = rx * tr.scale
    sx, sy = tr.pt(x0 + rx, y0)

    t.pensize(width)
    t.pencolor(outline)
    pen_up_to(t, sx, sy)
    if fill:
        t.fillcolor(fill)
        t.begin_fill()
    t.setheading(0)
    t.down()
    for _ in range(2):
        t.forward(max(0.0, wpx - 2*rpx)); t.circle(rpx, 90)
        t.forward(max(0.0, hpx - 2*rpx)); t.circle(rpx, 90)
    t.up()
    if fill:
        t.end_fill()

def draw_polygon_cm(t, tr, pts, fill=None, outline=COLOR_CONTOUR, width=LINE_WIDTH):
    if not pts: return
    # Arrondi auto pour coussins rectangulaires axis‑alignés
    if fill == COLOR_CUSHION and _is_axis_aligned_rect(pts):
        xs = [x for x, _ in pts[:-1]] if pts[0] == pts[-1] else [x for x, _ in pts]
        ys = [y for _, y in pts[:-1]] if pts[0] == pts[-1] else [y for _, y in pts]
        x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
        draw_rounded_rect_cm(t, tr, x0, y0, x1, y1, r_cm=CUSHION_ROUND_R_CM,
                             fill=fill, outline=outline, width=width)
        return
    # Fallback polygonal
    t.pensize(width); t.pencolor(outline)
    x0, y0 = tr.pt(*pts[0]); pen_up_to(t, x0, y0)
    if fill: t.fillcolor(fill); t.begin_fill()
    t.down()
    for x, y in pts[1:]:
        t.goto(*tr.pt(x, y))
    t.goto(x0, y0)
    if fill: t.end_fill()
    t.up()

# (Quadrillage & repères supprimés à la demande client → fonctions conservées mais non appelées)
def draw_grid_cm(t, tr, tx, ty, step, color, width):  # non utilisé
    pass

def draw_axis_labels_cm(t, tr, tx, ty, step=AXIS_LABEL_STEP, max_mark=AXIS_LABEL_MAX):  # non utilisé
    pass

def _unit(vx, vy):
    n = math.hypot(vx, vy)
    return (vx/n, vy/n) if n else (0, 0)

def draw_double_arrow_px(t, p1, p2, text=None, text_perp_offset_px=0, text_tang_shift_px=0):
    t.pensize(1.5); t.pencolor("black")
    pen_up_to(t, *p1); t.down(); t.goto(*p2); t.up()
    vx, vy = (p2[0]-p1[0], p2[1]-p1[1]); ux, uy = _unit(vx, vy); px, py = -uy, ux
    ah, spread = 12, 5
    for base, sgn in [(p1, +1), (p2, -1)]:
        a = (base[0] + ux*ah*sgn + px*spread, base[1] + uy*ah*sgn + py*spread)
        b = (base[0] + ux*ah*sgn - px*spread, base[1] + uy*ah*sgn - py*spread)
        pen_up_to(t, *base); t.down(); t.goto(*a); t.up()
        pen_up_to(t, *base); t.down(); t.goto(*b); t.up()
    if text:
        cx, cy = ((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0)
        tx = cx + px*text_perp_offset_px + ux*text_tang_shift_px
        ty = cy + py*text_perp_offset_px + uy*text_tang_shift_px
        pen_up_to(t, tx, ty); t.write(text, align="center", font=FONT_DIM)

def draw_double_arrow_vertical_cm(t, tr, x_cm, y0_cm, y1_cm, label):
    draw_double_arrow_px(t, tr.pt(x_cm, y0_cm), tr.pt(x_cm, y1_cm), text=label, text_perp_offset_px=+12)

def draw_double_arrow_horizontal_cm(t, tr, y_cm, x0_cm, x1_cm, label):
    draw_double_arrow_px(t, tr.pt(x0_cm, y_cm), tr.pt(x1_cm, y_cm), text=label,
                         text_perp_offset_px=-12, text_tang_shift_px=20)

def centroid(poly):
    return (sum(x for x,y in poly)/len(poly), sum(y for x,y in poly)/len(poly))

def label_poly(t, tr, poly, text, font=FONT_LABEL):
    cx, cy = centroid(poly); pen_up_to(t, *tr.pt(cx, cy))
    t.write(text, align="center", font=font)

def label_poly_offset_cm(t, tr, poly, text, dx_cm=0.0, dy_cm=0.0, font=FONT_LABEL):
    cx, cy = centroid(poly); x, y = tr.pt(cx + dx_cm, cy + dy_cm)
    pen_up_to(t, x, y); t.write(text, align="center", font=font)

def banquette_dims(poly):
    xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    L=max(max(xs)-min(xs), max(ys)-min(ys)); P=min(max(xs)-min(xs), max(ys)-min(ys))
    return int(round(L)), int(round(P))

def _split_mid_int(a, b):
    delta = b - a; L = abs(delta); left = L // 2
    return a + (left if delta >= 0 else -left)

def _rectU(x0, y0, x1, y1):
    return [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]

def _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0=None, seat_y1=None):
    """
    Construit 1 ou 2 rectangles verticaux (liste de polygones) pour un dossier.
    - [x0,x1] = épaisseur du dossier (ex: 0 → F0x)
    - [y0,y1] = étendue réelle du dossier à dessiner (tenue compte méridienne)
    - seat_y0/seat_y1 = bornes 'assise' complètes (sans méridienne) : si |seat_y1-seat_y0|>SPLIT_THRESHOLD
      on coupe au milieu de [seat_y0, seat_y1], mais seulement si la coupe tombe dans ]y0,y1[.
    """
    xL, xR = (min(x0, x1), max(x0, x1))
    yB, yT = (min(y0, y1), max(y0, y1))
    rects = []

    do_split = (seat_y0 is not None and seat_y1 is not None and abs(seat_y1 - seat_y0) > SPLIT_THRESHOLD)
    if do_split:
        ymid = _split_mid_int(seat_y0, seat_y1)
        if yB < ymid < yT:
            rects.append(_rectU(xL, yB, xR, ymid))
            rects.append(_rectU(xL, ymid, xR, yT))
            return rects

    rects.append(_rectU(xL, yB, xR, yT))
    return rects

def _build_dossier_horizontal_rects(x0, x1, y0, y1, seat_x0=None, seat_x1=None):
    """
    Construit 1 ou 2 rectangles horizontaux (liste de polygones) pour un dossier bas.
    - [x0,x1] = étendue réelle du dossier à dessiner (tenue compte méridienne)
    - [y0,y1] = épaisseur verticale du dossier (ex: 0 → F0y)
    - seat_x0/seat_x1 = bornes 'assise' complètes : si |seat_x1-seat_x0|>SPLIT_THRESHOLD
      on coupe au milieu de [seat_x0, seat_x1], mais seulement si la coupe tombe dans ]x0,x1[.
    """
    xL, xR = (min(x0, x1), max(x0, x1))
    yB, yT = (min(y0, y1), max(y0, y1))
    rects = []

    do_split = (seat_x0 is not None and seat_x1 is not None and abs(seat_x1 - seat_x0) > SPLIT_THRESHOLD)
    if do_split:
        xmid = _split_mid_int(seat_x0, seat_x1)
        if xL < xmid < xR:
            rects.append(_rectU(xL, yB, xmid, yT))
            rects.append(_rectU(xmid, yB, xR, yT))
            return rects

    rects.append(_rectU(xL, yB, xR, yT))
    return rects

def _poly_has_area(p):
    if not p or len(p) < 4: return False
    xs=[x for x,y in p]; ys=[y for x,y in p]
    return (max(xs)-min(xs) > 1e-9) and (max(ys)-min(ys) > 1e-9)

# Nouveau : fonction utilitaire pour annoter les dossiers et accoudoirs.
# Le texte d'épaisseur des dossiers (« 10 cm ») doit apparaître en bas du
# canapé plutôt que sur le dossier gauche.  On identifie donc le dossier
# le plus bas (celui dont la coordonnée y minimale est la plus petite)
# parmi les dossiers non dégénérés et on y place l'annotation centrée.
# Les accoudoirs sont systématiquement annotés avec « 15 cm ».
def _label_backrests_armrests(t, tr, polys):
    """
    Annotate the backrests and armrests with their thicknesses.

    The backrest thickness should be displayed as “10cm” and positioned on
    the bottom-most backrest rather than on the left side.  We scan the
    list of non-degenerate backrest polygons, pick the one whose lowest
    y‑coordinate is minimal (tie‑breaking on width), and annotate it at its
    centroid.  All armrests are labelled with “15cm”.

    Parameters
    ----------
    t : turtle-like drawing context
        The drawing turtle used to write text.
    tr : Transform
        The cm→px transform used for the current render.
    polys : dict
        Dictionary of polygons with keys including “dossiers” and “accoudoirs”.
    """
    # Sélection du polygone le plus bas et horizontal pour placer « 10cm ».
    # On priorise un dossier horizontal si présent ; à défaut, on cherche une banquette.
    candidate = None
    best_y = float("inf")
    best_w = 0.0
    # Fonction interne pour mettre à jour le meilleur choix à partir d'un ensemble de polygones
    def update_best(polys_list):
        nonlocal candidate, best_y, best_w
        for p in polys_list:
            if not _poly_has_area(p):
                continue
            xs = [pt[0] for pt in p]; ys = [pt[1] for pt in p]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
            # On cherche un polygone horizontal : largeur ≥ hauteur
            if width + 1e-9 < height:
                continue
            min_y = min(ys)
            # Choisir celui ayant la coordonnée y minimale, puis la plus grande largeur
            if (min_y < best_y) or (abs(min_y - best_y) < 1e-9 and width > best_w):
                best_y = min_y
                best_w = width
                candidate = p
    # Chercher d'abord dans les dossiers, puis dans les banquettes si rien trouvé
    update_best(polys.get("dossiers", []))
    if candidate is None:
        update_best(polys.get("banquettes", []))
    # Placer l'annotation « 10cm » si un candidat a été trouvé
    if candidate is not None:
        # Positionner simplement le texte au centre du polygone choisi.  Utiliser
        # un seul polygone évite de placer l'annotation sur une éventuelle
        # arrête issue d'une scission : le texte reste bien dans un morceau.
        label_poly(t, tr, candidate, "10cm", font=FONT_DOSSIER)
    # Annoter les accoudoirs.  L'accoudoir du « bas » doit être
    # étiqueté « 15 » (sans unité) afin d'alléger la légende ; les
    # autres accoudoirs conservent « 15cm ».  Le critère retenu
    # consiste à identifier l'accoudoir dont l'ordonnée la plus basse
    # (min_y) est minimale.  Si plusieurs accoudoirs partagent cette
    # même ordonnée minimale (par exemple, deux accoudoirs latéraux
    # horizontaux d'un canapé U), alors aucun n'est considéré comme
    # « bas » et tous restent annotés « 15cm ».
    bottom_arm = None
    min_y = None
    # Collecte des ordonnées minimales pour chaque accoudoir ayant une
    # surface non nulle.
    arm_miny = []
    for p in polys.get("accoudoirs", []):
        if not _poly_has_area(p):
            continue
        ys = [pt[1] for pt in p]
        arm_miny.append((p, min(ys)))
    if arm_miny:
        # Trouver la plus petite ordonnée y parmi les accoudoirs
        global_min = min(y for (_, y) in arm_miny)
        # Lister les candidats ayant cette ordonnée (tolérance sur les
        # comparaisons de flottants)
        candidates = [p for (p, y) in arm_miny if abs(y - global_min) < 1e-9]
        # S'il n'y a qu'un seul candidat, on le choisit comme accoudoir du bas
        if len(candidates) == 1:
            bottom_arm = candidates[0]
    # Appliquer les libellés appropriés à chaque accoudoir
    for p in polys.get("accoudoirs", []):
        if not _poly_has_area(p):
            continue
        label = "15" if (bottom_arm is not None and p is bottom_arm) else "15cm"
        label_poly(t, tr, p, label)

def _assert_banquettes_max_250(polys):
    for poly in polys.get("banquettes", []):
        L, P = banquette_dims(poly)
        if L > MAX_BANQUETTE:
            raise ValueError(f"Banquette de {L}×{P} cm > {MAX_BANQUETTE} cm — scission supplémentaire nécessaire.")

# =====================================================================
# ================  Outils légende & titres (lisibilité)  =============
# =====================================================================

def _draw_rect_px(t, x, y, w, h, fill=None, outline=COLOR_CONTOUR, width=1):
    t.pensize(width); t.pencolor(outline)
    pen_up_to(t, x, y)
    if fill:
        t.fillcolor(fill); t.begin_fill()
    t.setheading(0); t.down()
    for _ in range(2):
        t.forward(w); t.left(90); t.forward(h); t.left(90)
    t.up()
    if fill:
        t.end_fill()

def _wrap_text(text, max_len=28):
    words = str(text).split()
    if not words: return [""]
    lines=[]; cur=words[0]
    for w in words[1:]:
        if len(cur)+1+len(w) <= max_len:
            cur += " " + w
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines

def draw_title_center(t, tr, tx_cm, ty_cm, text):
    """Titre centré en haut de la scène, à l’intérieur de l’espace visible."""
    # Suppression du titre : cette fonction retourne immédiatement pour
    # éviter d'afficher un titre. Toutes les instructions suivantes
    # sont désormais ignorées.
    return
    left = tr.left_px; bottom = tr.bottom_px
    right = left + tx_cm*tr.scale; top = bottom + ty_cm*tr.scale
    cx = (left + right)/2.0
    y  = top - TITLE_MARGIN_PX
    lines = _wrap_text(text, max_len=34)
    for i, line in enumerate(lines):
        pen_up_to(t, cx, y - i*18)
        t.write(line, align="center", font=FONT_TITLE)

def draw_legend(t, tr, tx_cm, ty_cm, items=None, pos="top-right"):
    """
    Légende avec items = [(label, hex, name), ...]
      - pos: "top-right" (par défaut) ou "top-center" (pour U afin d'éviter recouvrement)
    """
    # Suppression de la légende : cette fonction retourne immédiatement pour
    # éviter d'afficher une légende. Toutes les instructions suivantes
    # sont désormais ignorées.
    return
    left = tr.left_px; bottom = tr.bottom_px
    right = left + tx_cm*tr.scale; top = bottom + ty_cm*tr.scale

    # Items / couleurs
    if not items:
        items = [
            ("Dossier",   COLOR_DOSSIER, None),
            ("Accoudoir", COLOR_ACC,     None),
            ("Coussins",  COLOR_CUSHION, None),
            ("Assise",    COLOR_ASSISE,  None),
        ]
    # Taille & position + placement "safe" (jamais sur le schéma)
    box = LEGEND_BOX_PX
    gap = LEGEND_GAP_PX
    # largeur texte (un peu plus pour nom de teinte)
    max_text_w_px = 220
    total_h = len(items) * (box) + (len(items) - 1) * gap
    total_w = box + 8 + max_text_w_px

    # Dimensions du fond de légende
    legend_w = total_w + 16
    legend_h = total_h + 16

    # Bords de l'écran (px)
    scr_left, scr_right = -WIN_W / 2.0, WIN_W / 2.0
    scr_bottom, scr_top = -WIN_H / 2.0, WIN_H / 2.0

    # Limites de la scène utile (schéma)
    # (déjà calculées : left, right, bottom, top)

    # Espaces libres autour du schéma
    free_top = scr_top - top
    free_right = scr_right - right
    free_left = left - scr_left
    free_bottom = bottom - scr_bottom  # pas utilisé mais conservé pour extensions

    def _clamp(v, a, b):
        return max(a, min(b, v))

    SAFE = LEGEND_SAFE_PX
    EDGE = LEGEND_EDGE_PX
    x0 = None; y0 = None

    if pos == "top-center":
        # 1) Idéal : au‑dessus du schéma, centré, à distance SAFE
        if free_top >= legend_h + SAFE:
            cx = (left + right) / 2.0
            x0 = _clamp(cx - total_w / 2.0, scr_left + EDGE, scr_right - EDGE - total_w)
            # y0 = "ligne de tête" des items ; le fond ira de (y0 - total_h - 8) à (y0 + 8)
            y0 = min(scr_top - EDGE, top + SAFE + total_h + 8)
        # 2) Sinon : à droite du schéma
        elif free_right >= legend_w + SAFE:
            x0 = min(scr_right - EDGE - total_w, right + SAFE + 8)
            y0 = min(scr_top - EDGE, top - 12)
        # 3) Sinon : à gauche du schéma
        elif free_left >= legend_w + SAFE:
            x0 = max(scr_left + EDGE, left - SAFE - total_w - 8)
            y0 = min(scr_top - EDGE, top - 12)
        # 4) Repli ultime : en haut‑centre, à l’intérieur (comportement d’avant)
        else:
            cx = (left + right) / 2.0
            x0 = _clamp(cx - total_w / 2.0, left + 12, right - total_w - 12)
            y0 = top - 12
    else:
        # pos = "top-right" → on privilégie la droite, sinon le dessus, puis la gauche
        if free_right >= legend_w + SAFE:
            x0 = min(scr_right - EDGE - total_w, right + SAFE + 8)
            y0 = min(scr_top - EDGE, top - 12)
        elif free_top >= legend_h + SAFE:
            x0 = _clamp(right - total_w, scr_left + EDGE, scr_right - EDGE - total_w)
            y0 = min(scr_top - EDGE, top + SAFE + total_h + 8)
        elif free_left >= legend_w + SAFE:
            x0 = max(scr_left + EDGE, left - SAFE - total_w - 8)
            y0 = min(scr_top - EDGE, top - 12)
        else:
            # Repli : ancien placement en haut‑droite à l’intérieur
            x0 = right - total_w - 12
            y0 = top - 12

    # Fond (léger)
    _draw_rect_px(
        t,
        x0 - 8,
        y0 - total_h - 8,
        total_w + 16,
        total_h + 16,
        fill="#ffffff",
        outline="#aaaaaa",
        width=1,
    )

    # Lignes
    cur_y = y0 - box
    for label, col, name in items:
        _draw_rect_px(t, x0, cur_y, box, box, fill=col, outline=COLOR_CONTOUR, width=1)
        pen_up_to(t, x0 + box + 8, cur_y + box/2 - 6)
        lbl = f"{label}" + ("" if not name else f" ({name})")
        t.write(lbl, align="left", font=FONT_LEGEND)
        cur_y -= (box + gap)

# =====================================================================
# ================  COUSSINS — utilitaires limites méridienne =========
# =====================================================================

def _lim_x(pts, key):
    """Récupère x d’extrémité pour dessin coussins : supporte <key>, <key>_mer et <key>_."""
    if f"{key}_mer" in pts: return pts[f"{key}_mer"][0]
    if f"{key}_"   in pts: return pts[f"{key}_"][0]
    return pts[key][0]

def _lim_y(pts, key):
    """Récupère y d’extrémité pour dessin coussins : supporte <key>, <key>_mer et <key>_."""
    if f"{key}_mer" in pts: return pts[f"{key}_mer"][1]
    if f"{key}_"   in pts: return pts[f"{key}_"][1]
    return pts[key][1]

# =====================================================================
# ================  COUSSINS — moteur "valise" (utilitaires)  =========
# =====================================================================

def _parse_coussins_spec(coussins):
    """
    Retourne un dict décrivant la spécification des coussins.

    - mode : "auto", "80-90", "fixed" ou "valise"
    - fixed : int si mode == "fixed" (taille globale unique)
    - range : (min, max) si mode == "valise" (plage de tailles autorisées)
    - same : bool si mode == "valise" (impose la même taille pour tous les côtés)

    Règles :
      "auto"    -> ancien auto (un seul standard global parmi 65, 80 ou 90)
      "80-90"   -> auto par côté, mais uniquement avec 80 ou 90 cm
      entier    -> taille globale fixe (toutes branches)
      "valise"  -> 60..100,  Δ global ≤ 5
      "p"       -> 60..74,   Δ global ≤ 5
      "g"       -> 76..100,  Δ global ≤ 5
      "s"       -> same global, 60..100
      "p:s"     -> same global, 60..74
      "g:s"     -> same global, 76..100
    """
    # Cas "fixed" déjà typé entier
    if isinstance(coussins, int):
        return {"mode": "fixed", "fixed": int(coussins)}

    s = str(coussins).strip().lower()

    # Auto global (65/80/90, même taille partout)
    if s == "auto":
        return {"mode": "auto"}

    # NOUVEAU : mode 80-90
    # Permet à chaque côté (bas / gauche / droite) de choisir
    # indépendamment entre 80 ou 90, suivant la meilleure optimisation.
    if s == "80-90":
        return {"mode": "80-90"}

    # Entier passé en texte
    if s.isdigit():
        return {"mode": "fixed", "fixed": int(s)}

    # Sinon : familles "valise"
    same = (":s" in s) or (s == "s")
    base = s.replace(":s", "")
    if base == "s":
        base = "valise"

    if base not in ("valise", "p", "g"):
        raise ValueError(f"Spécification coussins invalide: {coussins}")

    if base == "p":
        r = (60, 74)
    elif base == "g":
        r = (76, 100)
    else:
        r = (60, 100)

    return {"mode": "valise", "range": r, "same": bool(same)}

def _parse_traversins_spec(traversins, allowed={"g","b","d"}):
    """
    Renvoie un set parmi {'g','b','d'} selon la demande utilisateur.
    - traversins peut être None, 'g', 'd', 'b', 'g,d', ['g','d'], ...
    - allowed restreint selon le type de canapé.
    """
    if not traversins:
        return set()
    if isinstance(traversins, (list, tuple, set)):
        raw = {str(x).strip().lower() for x in traversins}
    else:
        raw = {p.strip().lower() for p in str(traversins).replace(";", ",").split(",") if p.strip()}
    return raw & set(allowed)

def _waste_and_count_1d(length, size):
    """Retourne (count, waste) pour un segment 1D de longueur 'length' avec modules de 'size'."""
    if length <= 0 or size <= 0:
        return 0, max(0, length)
    n = int(length // size)
    waste = length - n*size
    return n, waste

# ----- Traversins : dessin -----
def _draw_traversin_block(t, tr, x0, y0, x1, y1):
    draw_rounded_rect_cm(t, tr, x0, y0, x1, y1,
                         r_cm=CUSHION_ROUND_R_CM,
                         fill=COLOR_TRAVERSIN, outline=COLOR_CONTOUR, width=1)
    cx, cy = (x0+x1)/2.0, (y0+y1)/2.0
    pen_up_to(t, *tr.pt(cx, cy))
    # Affiche la dimension mise à jour des traversins (70×20 cm)
    t.write("70x20", align="center", font=FONT_CUSHION)

# ----- L-like / U / S1 : placement traversins -----
def _draw_traversins_simple_S1(t, tr, pts, profondeur, dossier, traversins):
    """
    Traversins S1 : positionnés à la fin du dossier.
    - Si méridienne à gauche/droite, on s'aligne sur D0_m / Dx_m.
    """
    if not traversins:
        return 0
    y_base = DOSSIER_THICK if dossier else 0
    usable_h = max(0.0, profondeur - y_base)
    y0 = y_base + max(0.0, (usable_h - TRAVERSIN_LEN)/2.0)
    y1 = y0 + min(TRAVERSIN_LEN, usable_h)

    n = 0
    if "g" in traversins:
        # fin du dossier côté gauche
        x0 = (pts["D0_m"][0] if "D0_m" in pts else (pts["D0"][0] if "D0" in pts else pts["B0"][0]))
        x1 = x0 + TRAVERSIN_THK
        _draw_traversin_block(t, tr, x0, y0, x1, y1); n += 1
    if "d" in traversins:
        # fin du dossier côté droit
        x1 = (pts["Dx_m"][0] if "Dx_m" in pts else (pts["Dx"][0] if "Dx" in pts else pts["Bx"][0]))
        x0 = x1 - TRAVERSIN_THK
        _draw_traversin_block(t, tr, x0, y0, x1, y1); n += 1
    return n

def _draw_traversins_L_like(t, tr, pts, profondeur, traversins):
    """
    Placement des TR pour les formes 'L-like' (LNF v1/v2, LF).
    - 'g'  (gauche, horizontal) : collé sur la FIN DE BANQUETTE gauche (segment By–By2, ignorer *_mer)
    - 'b'  (bas, vertical)      : collé sur l’EXTRÉMITÉ DE BANQUETTE (Bx2–Bx),
                                  même en présence d’une méridienne (on ignore *_mer)
    """
    if not traversins:
        return 0

    F0x, F0y = pts["F0"]
    depth_len = min(TRAVERSIN_LEN, max(0.0, profondeur))
    n = 0

    # --- Gauche (horizontal) → collé sur la FIN DE BANQUETTE (segment By–By2) ---
    if "g" in traversins:
        # Coller à la FIN DE BANQUETTE (segment By–By2), et ignorer toute version *_mer
        y_end = pts["By"][1] if "By" in pts else (F0y + profondeur)
        y0 = y_end - TRAVERSIN_THK
        y1 = y_end
        _draw_traversin_block(t, tr, F0x, y0, F0x + depth_len, y1)
        n += 1

    # --- Bas (vertical) → FIN DE BANQUETTE (Bx2–Bx), pas fin de dossier ---
    if "b" in traversins:
        # On force Bx/Bx2 (et surtout PAS Bx_mer) pour coller au bord de banquette
        if   "Bx"  in pts: x_end = pts["Bx"][0]
        elif "Bx2" in pts: x_end = pts["Bx2"][0]
        else:
            # Secours (très improbable) : retomber sur une des anciennes clés ou un _lim
            if   "DxR" in pts: x_end = pts["DxR"][0]
            elif "Dx2" in pts: x_end = pts["Dx2"][0]
            elif "Dx"  in pts: x_end = pts["Dx"][0]
            else:              x_end = _lim_x(pts, "Bx")

        x0 = x_end - TRAVERSIN_THK
        x1 = x_end
        _draw_traversin_block(t, tr, x0, F0y, x1, F0y + depth_len)
        n += 1

    return n

def _u_right_col_x(variant, pts):
    return pts["Bx"][0] if variant in ("v1","v4") else pts["F02"][0]

def _draw_traversins_U_common(t, tr, variant, pts, profondeur, traversins):
    """
    U v1..v4 : traversins STRICTEMENT sur les segments de dossier internes :
      - gauche  → segment By–By2
      - droite  → segment By3–By4
    On ignore toute version 'avec _' (méridienne) et on n'utilise pas F02 ici.
    """
    if not traversins:
        return 0

    # Longueur du traversin posée dans le sens X (horizontal)
    depth_len = min(TRAVERSIN_LEN, max(0.0, float(profondeur)))
    n = 0

    # --- Gauche : By–By2 (alignement au début du segment)
    if "g" in traversins:
        seg_min, seg_max, y_line = _segment_x_limits(pts, "By", "By2")
        x0, x1 = _clamp_to_segment(seg_min, depth_len, seg_min, seg_max, align="start")
        y0 = y_line - TRAVERSIN_THK
        y1 = y_line
        _draw_traversin_block(t, tr, x0, y0, x1, y1)
        n += 1

    # --- Droite : By3–By4 (alignement à la fin du segment)
    if "d" in traversins:
        seg_min, seg_max, y_line = _segment_x_limits(pts, "By3", "By4")
        x0, x1 = _clamp_to_segment(seg_max, depth_len, seg_min, seg_max, align="end")
        y0 = y_line - TRAVERSIN_THK
        y1 = y_line
        _draw_traversin_block(t, tr, x0, y0, x1, y1)
        n += 1

    return n

def _draw_traversins_U_side_F02(t, tr, pts, profondeur, traversins):
    """
    U1F / U2f : traversins STRICTEMENT sur les segments de dossier internes :
      - gauche  → segment By–By2
      - droite  → segment By3–By4
    On ignore complètement F02 pour le placement des traversins.
    """
    if not traversins:
        return 0

    depth_len = min(TRAVERSIN_LEN, max(0.0, float(profondeur)))
    n = 0

    # --- Gauche : By–By2 (début du segment)
    if "g" in traversins:
        seg_min, seg_max, y_line = _segment_x_limits(pts, "By", "By2")
        x0, x1 = _clamp_to_segment(seg_min, depth_len, seg_min, seg_max, align="start")
        y0 = y_line - TRAVERSIN_THK
        y1 = y_line
        _draw_traversin_block(t, tr, x0, y0, x1, y1)
        n += 1

    # --- Droite : By3–By4 (fin du segment)
    if "d" in traversins:
        seg_min, seg_max, y_line = _segment_x_limits(pts, "By3", "By4")
        x0, x1 = _clamp_to_segment(seg_max, depth_len, seg_min, seg_max, align="end")
        y0 = y_line - TRAVERSIN_THK
        y1 = y_line
        _draw_traversin_block(t, tr, x0, y0, x1, y1)
        n += 1

    return n

# =====================================================================
# ================  COUSSINS — moteur "valise" (utilitaires)  =========
# =====================================================================

def _apply_traversin_limits_L_like(pts, x_end_key, y_end_key, traversins):
    x_end = _lim_x(pts, x_end_key); y_end = _lim_y(pts, y_end_key)
    if traversins:
        if "b" in traversins: x_end -= TRAVERSIN_THK
        if "g" in traversins: y_end -= TRAVERSIN_THK
    return x_end, y_end

def _eval_L_like_counts(pts, size_bas, size_g, shift_bas, x_end_key="Bx", y_end_key="By", traversins=None):
    F0x, F0y = pts["F0"]
    x_end, y_end = _apply_traversin_limits_L_like(pts, x_end_key, y_end_key, traversins)

    xs = F0x + (CUSHION_DEPTH if shift_bas else 0)
    xe = x_end
    y0 = F0y + (0 if shift_bas else CUSHION_DEPTH)
    ye = y_end

    len_b = max(0, xe - xs)
    len_g = max(0, ye - y0)

    nb_b, wb = _waste_and_count_1d(len_b, size_bas)
    nb_g, wg = _waste_and_count_1d(len_g, size_g)
    waste_tot = wb + wg
    cover = nb_b*size_bas + nb_g*size_g
    return {
        "counts": {"bas": nb_b, "gauche": nb_g},
        "waste": waste_tot,
        "cover": cover,
        "geom": {"xs": xs, "xe": xe, "y0": y0, "ye": ye}
    }

def _optimize_valise_L_like(pts, rng, same, x_end_key="Bx", y_end_key="By", traversins=None):
    best = None
    r0, r1 = rng
    for size_g in range(r0, r1+1):
        cand_b = [size_g] if same else range(r0, r1+1)
        for size_b in cand_b:
            if abs(size_b - size_g) > 5:
                continue
            eval_A = _eval_L_like_counts(pts, size_b, size_g, shift_bas=False, x_end_key=x_end_key, y_end_key=y_end_key, traversins=traversins)
            eval_B = _eval_L_like_counts(pts, size_b, size_g, shift_bas=True,  x_end_key=x_end_key, y_end_key=y_end_key, traversins=traversins)
            e = min([eval_A, eval_B], key=lambda E: (E["waste"], -E["cover"], -size_b, -size_g))
            score = (e["waste"], -e["cover"], -size_b, -size_g)
            if (best is None) or (score < best["score"]):
                best = {"score": score, "sizes": {"bas": size_b, "gauche": size_g}, "eval": e,
                        "shift_bas": (e is eval_B)}
    return best

def _optimize_80_90_L_like(pts, x_end_key="Bx", y_end_key="By", traversins=None):
    """
    Variante spéciale pour le mode "80-90" sur les canapés en L / LF.

    Contrairement à "auto" qui impose une seule taille globale,
    chaque côté (bas / gauche) peut choisir 80 ou 90 cm
    indépendamment, en minimisant le déchet et en maximisant la
    couverture.
    """
    candidates = (80, 90)
    best = None
    for size_g in candidates:
        for size_b in candidates:
            # Deux orientations possibles : bas décalé ou non
            eval_A = _eval_L_like_counts(
                pts,
                size_b,
                size_g,
                shift_bas=False,
                x_end_key=x_end_key,
                y_end_key=y_end_key,
                traversins=traversins,
            )
            eval_B = _eval_L_like_counts(
                pts,
                size_b,
                size_g,
                shift_bas=True,
                x_end_key=x_end_key,
                y_end_key=y_end_key,
                traversins=traversins,
            )
            # Meilleure orientation pour ce couple de tailles
            e = min(
                (eval_A, eval_B),
                key=lambda E: (E["waste"], -E["cover"], -size_b, -size_g),
            )
            score = (e["waste"], -e["cover"], -size_b, -size_g)
            if best is None or score < best["score"]:
                best = {
                    "score": score,
                    "sizes": {"bas": size_b, "gauche": size_g},
                    "eval": e,
                    "shift_bas": (e is eval_B),
                }
    return best

def _draw_L_like_with_sizes(t, tr, pts, sizes, shift_bas, x_end_key="Bx", y_end_key="By", traversins=None):
    F0x, F0y = pts["F0"]
    x_end, y_end = _apply_traversin_limits_L_like(pts, x_end_key, y_end_key, traversins)

    # bas
    xs = F0x + (CUSHION_DEPTH if shift_bas else 0)
    xe = x_end; yb = F0y
    nb = 0; x = xs
    sb = sizes["bas"]
    while x + sb <= xe + 1e-6:
        poly = [(x,yb), (x+sb,yb), (x+sb,yb+CUSHION_DEPTH), (x,yb+CUSHION_DEPTH), (x,yb)]
        draw_polygon_cm(t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1)
        label_poly(t, tr, poly, f"{sb}", font=FONT_CUSHION)
        x += sb; nb += 1

    # gauche
    yg0 = F0y + (0 if shift_bas else CUSHION_DEPTH)
    yg1 = y_end; xg = F0x
    ng = 0; y = yg0
    sg = sizes["gauche"]
    while y + sg <= yg1 + 1e-6:
        poly = [(xg,y), (xg+CUSHION_DEPTH,y), (xg+CUSHION_DEPTH,y+sg), (xg,y+sg), (xg,y)]
        draw_polygon_cm(t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1)
        label_poly(t, tr, poly, f"{sg}", font=FONT_CUSHION)
        y += sg; ng += 1

    return nb + ng, sb, sg

# ----- U2f : évaluation / dessin -----
def _eval_U2f_counts(pts, sb, sg, sd, shiftL, shiftR, traversins=None):
    F0x, F0y = pts["F0"]
    F02x = pts["F02"][0]
    y_end_L = pts.get("By_", pts["By"])[1]
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK

    xs = F0x + (CUSHION_DEPTH if shiftL else 0)
    xe = F02x - (CUSHION_DEPTH if shiftR else 0)
    yL0 = F0y + (0 if shiftL else CUSHION_DEPTH)
    yR0 = F0y + (0 if shiftR else CUSHION_DEPTH)

    len_b = max(0, xe - xs)
    len_g = max(0, y_end_L - yL0)
    len_d = max(0, y_end_R - yR0)

    nb, wb = _waste_and_count_1d(len_b, sb)
    ng, wg = _waste_and_count_1d(len_g, sg)
    nd, wd = _waste_and_count_1d(len_d, sd)
    waste = wb + wg + wd
    cover = nb*sb + ng*sg + nd*sd
    return {"counts": {"bas": nb, "gauche": ng, "droite": nd},
            "waste": waste, "cover": cover,
            "geom": {"xs": xs, "xe": xe, "yL0": yL0, "yR0": yR0}}

def _optimize_valise_U2f(pts, rng, same, traversins=None):
    best=None; r0,r1=rng
    for sg in range(r0, r1+1):
        cand_b = [sg] if same else range(r0, r1+1)
        for sb in cand_b:
            cand_d = [sg] if same else range(r0, r1+1)
            for sd in cand_d:
                if max(sb, sg, sd) - min(sb, sg, sd) > 5:
                    continue
                E = []
                for sl in (False, True):
                    for sr in (False, True):
                        E.append(_eval_U2f_counts(pts, sb, sg, sd, sl, sr, traversins=traversins))
                e = min(E, key=lambda x: (x["waste"], -x["cover"], -sb, -sg, -sd))
                score = (e["waste"], -e["cover"], -sb, -sg, -sd)
                if (best is None) or (score < best["score"]):
                    best = {"score": score, "sizes": {"bas": sb, "gauche": sg, "droite": sd}, "eval": e}
    if best:
        chosen = best["eval"]
        for sl in (False, True):
            for sr in (False, True):
                chk = _eval_U2f_counts(pts, best["sizes"]["bas"], best["sizes"]["gauche"], best["sizes"]["droite"], sl, sr, traversins=traversins)
                if abs(chk["waste"] - chosen["waste"])<1e-9 and chk["cover"]==chosen["cover"]:
                    best["shiftL"], best["shiftR"] = sl, sr
                    return best
    return best

def _optimize_80_90_U2f(pts, traversins=None):
    """
    Variante spéciale pour le mode "80-90" sur les canapés en U2f.

    Chaque côté (bas / gauche / droite) peut choisir 80 ou 90 cm
    indépendamment, en cherchant le meilleur compromis déchet / couverture.
    """
    candidates = (80, 90)
    best = None
    for sg in candidates:
        for sb in candidates:
            for sd in candidates:
                E = []
                for sl in (False, True):
                    for sr in (False, True):
                        E.append(
                            _eval_U2f_counts(
                                pts,
                                sb,
                                sg,
                                sd,
                                sl,
                                sr,
                                traversins=traversins,
                            )
                        )
                e = min(
                    E,
                    key=lambda x: (
                        x["waste"],
                        -x["cover"],
                        -sb,
                        -sg,
                        -sd,
                    ),
                )
                score = (e["waste"], -e["cover"], -sb, -sg, -sd)
                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "sizes": {"bas": sb, "gauche": sg, "droite": sd},
                        "eval": e,
                    }

    # Retrouver les shifts correspondant à la solution choisie
    if best:
        chosen = best["eval"]
        for sl in (False, True):
            for sr in (False, True):
                chk = _eval_U2f_counts(
                    pts,
                    best["sizes"]["bas"],
                    best["sizes"]["gauche"],
                    best["sizes"]["droite"],
                    sl,
                    sr,
                    traversins=traversins,
                )
                if (
                    abs(chk["waste"] - chosen["waste"]) < 1e-9
                    and chk["cover"] == chosen["cover"]
                ):
                    best["shiftL"], best["shiftR"] = sl, sr
                    return best
    return best

def _draw_U2f_with_sizes(t, tr, pts, sizes, shiftL, shiftR, traversins=None):
    F0x, F0y = pts["F0"]
    F02x = pts["F02"][0]
    y_end_L = pts.get("By_", pts["By"])[1]
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK

    # Bas
    xs = F0x + (CUSHION_DEPTH if shiftL else 0)
    xe = F02x - (CUSHION_DEPTH if shiftR else 0)
    yb = F0y; sb = sizes["bas"]; nb=0; x=xs
    while x + sb <= xe + 1e-6:
        poly=[(x,yb),(x+sb,yb),(x+sb,yb+CUSHION_DEPTH),(x,yb+CUSHION_DEPTH),(x,yb)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{sb}",font=FONT_CUSHION)
        x+=sb; nb+=1

    # Gauche
    yL0 = F0y + (0 if shiftL else CUSHION_DEPTH)
    xg = F0x; sg = sizes["gauche"]; ng=0; y=yL0
    while y + sg <= y_end_L + 1e-6:
        poly=[(xg,y),(xg+CUSHION_DEPTH,y),(xg+CUSHION_DEPTH,y+sg),(xg,y+sg),(xg,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{sg}",font=FONT_CUSHION)
        y+=sg; ng+=1

    # Droite
    yR0 = F0y + (0 if shiftR else CUSHION_DEPTH)
    xr = F02x; sd = sizes["droite"]; nd=0; y=yR0
    while y + sd <= y_end_R + 1e-6:
        poly=[(xr-CUSHION_DEPTH,y),(xr,y),(xr,y+sd),(xr-CUSHION_DEPTH,y+sd),(xr-CUSHION_DEPTH,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{sd}",font=FONT_CUSHION)
        y+=sd; nd+=1

    return nb+ng+nd

def _draw_cushions_U2f_optimized(t, tr, pts, size, traversins=None):
    F0x, F0y = pts["F0"]
    F02x = pts["F02"][0]
    y_end_L = pts.get("By_", pts["By"])[1]
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK

    def cnt_h(x0, x1):
        return int(max(0, x1-x0) // size)
    def cnt_v(y0, y1):
        return int(max(0, y1-y0) // size)

    def score(shift_left, shift_right):
        xs = F0x + (CUSHION_DEPTH if shift_left else 0)
        xe = F02x - (CUSHION_DEPTH if shift_right else 0)
        bas = cnt_h(xs, xe)
        yL0 = F0y + (0 if shift_left else CUSHION_DEPTH)
        yR0 = F0y + (0 if shift_right else CUSHION_DEPTH)
        g = cnt_v(yL0, y_end_L)
        d = cnt_v(yR0, y_end_R)
        w = (max(0, xe-xs) % size) + (max(0, y_end_L-yL0) % size) + (max(0, y_end_R-yR0) % size)
        return (bas+g+d, -w), xs, xe, yL0, yR0

    candidates = [score(False,False), score(True,False), score(False,True), score(True,True)]
    best = max(candidates, key=lambda s: s[0])
    _, xs, xe, yL0, yR0 = best

    count = 0
    # Bas
    y, x = F0y, xs
    while x + size <= xe + 1e-6:
        poly = [(x,y),(x+size,y),(x+size,y+CUSHION_DEPTH),(x,y+CUSHION_DEPTH),(x,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        x += size; count += 1
    # Gauche
    x, y = F0x, yL0
    while y + size <= y_end_L + 1e-6:
        poly = [(x,y),(x+CUSHION_DEPTH,y),(x+CUSHION_DEPTH,y+size),(x,y+size),(x,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        y += size; count += 1
    # Droite
    x, y = F02x, yR0
    while y + size <= y_end_R + 1e-6:
        poly = [(x-CUSHION_DEPTH,y),(x,y),(x,y+size),(x-CUSHION_DEPTH,y+size),(x-CUSHION_DEPTH,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        y += size; count += 1
    return count

# -----------------------------------------------------------------------------
# Nouveau calcul des labels pour les banquettes
def _compute_banquette_labels(polys):
    """
    Génère des étiquettes pour chaque banquette afin d'afficher des
    dimensions « mousse » cohérentes lorsqu'il y a des scissions.

    Plutôt que de numéroter toutes les banquettes consécutivement (1, 2, 3…),
    cette fonction regroupe les morceaux appartenant à la même branche (gauche,
    bas, droite) et leur attribue le même numéro suivi d'un suffixe « -bis »
    pour les scissions.  L'ordre des branches est déterminé à partir de la
    géométrie des banquettes : les morceaux verticaux à gauche, les morceaux
    horizontaux (bas) puis les morceaux verticaux à droite.  Si une branche
    n'existe pas (par exemple sur un canapé en L), les numéros restent
    contigus.

    Paramètres
    ----------
    polys : dict
        Dictionnaire contenant les polygones du canapé, notamment la clé
        ``"banquettes"`` avec la liste des polygones des assises.

    Retourne
    -------
    list of str
        Une liste d'étiquettes (``"1"``, ``"1-bis"``, ``"2"``, etc.)
        correspondant à chaque banquette dans l'ordre où elles apparaissent.
    """
    banquettes = polys.get("banquettes", [])
    n = len(banquettes)
    # Aucun banquette : aucune étiquette
    if n == 0:
        return []

    # Récupérer les dimensions et centres de chaque banquette pour déterminer
    # leur orientation (verticale ou horizontale) et leur position.
    info = []  # Liste de tuples (orientation, cx, cy)
    for poly in banquettes:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Orientation : horizontale si largeur strictement > hauteur,
        # verticale sinon (y compris carrée)
        orientation = 'horiz' if bb_w > bb_h else 'vert'
        cx = sum(xs) / float(len(xs))
        cy = sum(ys) / float(len(ys))
        info.append((orientation, cx, cy))

    # Séparer les indices verticaux et horizontaux
    vertical_indices = [i for i, (ori, cx, cy) in enumerate(info) if ori == 'vert']
    horizontal_indices = [i for i, (ori, cx, cy) in enumerate(info) if ori == 'horiz']

    # Attribuer un identifiant de branche à chaque banquette (L, M ou R)
    branch_ids = [None] * n
    if len(vertical_indices) == 0:
        # Toutes les banquettes sont horizontales : une seule branche
        for idx in horizontal_indices:
            branch_ids[idx] = 'M'
    elif len(vertical_indices) == 1:
        # Une seule verticale : elle constitue une branche unique ;
        # les horizontales constituent la seconde branche si présentes.
        v_idx = vertical_indices[0]
        branch_ids[v_idx] = 'L'
        for idx in horizontal_indices:
            branch_ids[idx] = 'M'
    else:
        # Au moins deux verticales : séparer gauche et droite selon l'abscisse
        xs_vert = [info[i][1] for i in vertical_indices]
        min_x = min(xs_vert)
        max_x = max(xs_vert)
        # Milieu pour distinguer gauche et droite ; en cas d'égalité,
        # toutes les verticales de gauche sont celles dont le centre est
        # strictement inférieur ou égal au milieu.
        mid_x = (min_x + max_x) / 2.0
        for i in vertical_indices:
            cx = info[i][1]
            if cx <= mid_x:
                branch_ids[i] = 'L'
            else:
                branch_ids[i] = 'R'
        for i in horizontal_indices:
            branch_ids[i] = 'M'
    # Si certains identifiants n'ont pas été attribués (cas dégénéré),
    # les rattacher à la branche horizontale par défaut.
    for i in range(n):
        if branch_ids[i] is None:
            branch_ids[i] = 'M'

    # Construire l'ordre des branches selon leur première apparition pour
    # produire des numéros contigus. Exemple : ['L','L','M','M','R']
    # -> ordre = ['L','M','R'] -> mapping = {'L':1,'M':2,'R':3}
    branch_order = []
    for b_id in branch_ids:
        if b_id not in branch_order:
            branch_order.append(b_id)
    mapping = {b_id: idx for idx, b_id in enumerate(branch_order, start=1)}

    # Pour chaque banquette, créer l'étiquette en fonction du nombre de
    # morceaux déjà rencontrés dans la même branche.
    count_so_far = {num: 0 for num in mapping.values()}
    labels = []
    for b_id in branch_ids:
        b_num = mapping[b_id]
        if count_so_far[b_num] == 0:
            labels.append(str(b_num))
        else:
            labels.append(f"{b_num}-bis")
        count_so_far[b_num] += 1
    return labels

# ----- U1F : évaluation / dessin -----
def _eval_U1F_counts(pts, sb, sg, sd, shiftL, shiftR, traversins=None):
    F0x, F0y = pts["F0"]; F02x = pts["F02"][0]
    y_end_L = pts["By_cush"][1]; y_end_R = pts["By4_cush"][1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK
    xs = F0x + (CUSHION_DEPTH if shiftL else 0)
    xe = F02x - (CUSHION_DEPTH if shiftR else 0)
    yL0 = F0y + (0 if shiftL else CUSHION_DEPTH)
    yR0 = F0y + (0 if shiftR else CUSHION_DEPTH)
    len_b = max(0, xe-xs); len_g=max(0, y_end_L-yL0); len_d=max(0, y_end_R-yR0)
    nb, wb = _waste_and_count_1d(len_b, sb)
    ng, wg = _waste_and_count_1d(len_g, sg)
    nd, wd = _waste_and_count_1d(len_d, sd)
    waste = wb+wg+wd; cover=nb*sb+ng*sg+nd*sd
    return {"counts":{"bas":nb,"gauche":ng,"droite":nd},"waste":waste,"cover":cover}

def _optimize_valise_U1F(pts, rng, same, traversins=None):
    best=None; r0,r1=rng
    for sg in range(r0,r1+1):
        for sb in ([sg] if same else range(r0,r1+1)):
            for sd in ([sg] if same else range(r0,r1+1)):
                if max(sb,sg,sd)-min(sb,sg,sd) > 5:
                    continue
                E=[]
                for sl in (False,True):
                    for sr in (False,True):
                        E.append(_eval_U1F_counts(pts,sb,sg,sd,sl,sr,traversins=traversins))
                e = min(E, key=lambda x: (x["waste"], -x["cover"], -sb, -sg, -sd))
                score=(e["waste"], -e["cover"], -sb, -sg, -sd)
                if (best is None) or (score < best["score"]):
                    best={"score":score, "sizes":{"bas":sb,"gauche":sg,"droite":sd}, "shifts":("?", "?")}
    # Retrouver shifts exacts
    if best:
        tgt = best["score"]
        for sl in (False,True):
            for sr in (False,True):
                chk=_eval_U1F_counts(pts,best["sizes"]["bas"],best["sizes"]["gauche"],best["sizes"]["droite"],sl,sr,traversins=traversins)
                score=(chk["waste"], -chk["cover"], -best["sizes"]["bas"], -best["sizes"]["gauche"], -best["sizes"]["droite"])
                if score==tgt:
                    best["shifts"]=(sl,sr); break
    return best

def _optimize_80_90_U1F(pts, traversins=None):
    """
    Variante spéciale pour le mode "80-90" sur les canapés U1F.

    Chaque côté (bas / gauche / droite) peut choisir 80 ou 90 cm
    indépendamment.
    """
    candidates = (80, 90)
    best = None
    for sg in candidates:
        for sb in candidates:
            for sd in candidates:
                E = []
                for sl in (False, True):
                    for sr in (False, True):
                        E.append(
                            _eval_U1F_counts(
                                pts,
                                sb,
                                sg,
                                sd,
                                sl,
                                sr,
                                traversins=traversins,
                            )
                        )
                e = min(
                    E,
                    key=lambda x: (
                        x["waste"],
                        -x["cover"],
                        -sb,
                        -sg,
                        -sd,
                    ),
                )
                score = (e["waste"], -e["cover"], -sb, -sg, -sd)
                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "sizes": {"bas": sb, "gauche": sg, "droite": sd},
                        "eval": e,
                        "shifts": ("?", "?"),
                    }

    # Retrouver les shifts exacts
    if best:
        tgt = best["score"]
        sb = best["sizes"]["bas"]
        sg = best["sizes"]["gauche"]
        sd = best["sizes"]["droite"]
        for sl in (False, True):
            for sr in (False, True):
                chk = _eval_U1F_counts(
                    pts,
                    sb,
                    sg,
                    sd,
                    sl,
                    sr,
                    traversins=traversins,
                )
                score = (
                    chk["waste"],
                    -chk["cover"],
                    -sb,
                    -sg,
                    -sd,
                )
                if score == tgt:
                    best["shifts"] = (sl, sr)
                    return best
    return best

def _draw_U1F_with_sizes(t,tr,pts,sizes,shiftL,shiftR,traversins=None):
    F0x, F0y = pts["F0"]; F02x=pts["F02"][0]
    y_end_L = pts["By_cush"][1]; y_end_R=pts["By4_cush"][1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK

    # Bas
    xs = F0x + (CUSHION_DEPTH if shiftL else 0)
    xe = F02x - (CUSHION_DEPTH if shiftR else 0)
    sb=sizes["bas"]; nb=0; x=xs; y=F0y
    while x + sb <= xe + 1e-6:
        poly=[(x,y),(x+sb,y),(x+sb,y+CUSHION_DEPTH),(x,y+CUSHION_DEPTH),(x,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{sb}",font=FONT_CUSHION)
        nb+=1; x+=sb

    # Gauche
    yL0 = F0y + (0 if shiftL else CUSHION_DEPTH)
    sg=sizes["gauche"]; ng=0; xg=F0x; y_=yL0
    while y_ + sg <= y_end_L + 1e-6:
        poly=[(xg,y_),(xg+CUSHION_DEPTH,y_),(xg+CUSHION_DEPTH,y_+sg),(xg,y_+sg),(xg,y_)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{sg}",font=FONT_CUSHION)
        ng+=1; y_+=sg

    # Droite
    yR0 = F0y + (0 if shiftR else CUSHION_DEPTH)
    sd=sizes["droite"]; nd=0; xr=F02x; y_=yR0
    while y_ + sd <= y_end_R + 1e-6:
        poly=[(xr-CUSHION_DEPTH,y_),(xr,y_),(xr,y_+sd),(xr-CUSHION_DEPTH,y_+sd),(xr-CUSHION_DEPTH,y_)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{sd}",font=FONT_CUSHION)
        nd+=1; y_+=sd

    return nb+ng+nd

# ----- U (no fromage) : fonctions de choix et dessin coussins -----
def _u_variant_x_end(variant, pts):
    if variant in ("v1","v4"):
        return pts["Bx"][0]
    else:
        return pts["F02"][0]

def _eval_U_counts(variant, pts, drawn, sb, sg, sd, shiftL, shiftR, traversins=None):
    """
    Evaluate how many cushions of sizes ``sb``, ``sg`` and ``sd`` will fit on
    the bottom, left and right branches of a U‑shaped sofa, considering
    possible méridienne limits.
    """
    F0x, F0y = pts["F0"]
    x_end = _u_variant_x_end(variant, pts)
    xs = F0x + (CUSHION_DEPTH if shiftL else 0)
    xe = x_end - (CUSHION_DEPTH if shiftR else 0)

    y_end_L = pts.get("By_", pts["By"])[1]
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins:
        if "g" in traversins:
            y_end_L -= TRAVERSIN_THK
        if "d" in traversins:
            y_end_R -= TRAVERSIN_THK
    yL0 = F0y + (0 if (not drawn.get("D1", False) or shiftL) else CUSHION_DEPTH)
    has_right = drawn.get("D4", False) or drawn.get("D5", False)
    yR0 = F0y + (0 if (not has_right or shiftR) else CUSHION_DEPTH)

    nb, wb = _waste_and_count_1d(max(0, xe - xs), sb)
    ng, wg = _waste_and_count_1d(max(0, y_end_L - yL0), sg)
    nd, wd = _waste_and_count_1d(max(0, y_end_R - yR0), sd)
    waste = wb + wg + wd
    cover = nb * sb + ng * sg + nd * sd
    return {
        "counts": {"bas": nb, "gauche": ng, "droite": nd},
        "waste": waste,
        "cover": cover,
    }

def _optimize_valise_U(variant, pts, drawn, rng, same, traversins=None):
    best=None; r0,r1=rng
    for sg in range(r0,r1+1):
        for sb in ([sg] if same else range(r0,r1+1)):
            for sd in ([sg] if same else range(r0,r1+1)):
                if max(sb,sg,sd)-min(sb,sg,sd) > 5:
                    continue
                E=[]
                for sl in (False,True):
                    for sr in (False,True):
                        E.append(_eval_U_counts(variant, pts, drawn, sb, sg, sd, sl, sr, traversins=traversins))
                e = min(E, key=lambda x: (x["waste"], -x["cover"], -sb, -sg, -sd))
                score=(e["waste"], -e["cover"], -sb, -sg, -sd)
                if (best is None) or (score < best["score"]):
                    best={"score":score, "sizes":{"bas":sb,"gauche":sg,"droite":sd}}
    if best:
        tgt=best["score"]
        for sl in (False,True):
            for sr in (False,True):
                chk=_eval_U_counts(variant, pts, drawn, best["sizes"]["bas"], best["sizes"]["gauche"], best["sizes"]["droite"], sl, sr, traversins=traversins)
                score=(chk["waste"], -chk["cover"], -best["sizes"]["bas"], -best["sizes"]["gauche"], -best["sizes"]["droite"])
                if score==tgt:
                    best["shiftL"], best["shiftR"] = sl, sr
                    break
    return best

def _optimize_80_90_U(variant, pts, drawn, traversins=None):
    """
    Variante spéciale pour le mode "80-90" sur les canapés en U (sans angle fromage).

    Chaque côté (bas / gauche / droite) peut choisir 80 ou 90 cm
    indépendamment.
    """
    candidates = (80, 90)
    best = None
    for sg in candidates:
        for sb in candidates:
            for sd in candidates:
                E = []
                for sl in (False, True):
                    for sr in (False, True):
                        E.append(
                            _eval_U_counts(
                                variant,
                                pts,
                                drawn,
                                sb,
                                sg,
                                sd,
                                sl,
                                sr,
                                traversins=traversins,
                            )
                        )
                e = min(
                    E,
                    key=lambda x: (
                        x["waste"],
                        -x["cover"],
                        -sb,
                        -sg,
                        -sd,
                    ),
                )
                score = (e["waste"], -e["cover"], -sb, -sg, -sd)
                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "sizes": {"bas": sb, "gauche": sg, "droite": sd},
                        "eval": e,
                        "shiftL": False,
                        "shiftR": False,
                    }

    # Retrouver les shifts correspondant à la meilleure solution
    if best:
        chosen = best["eval"]
        sb = best["sizes"]["bas"]
        sg = best["sizes"]["gauche"]
        sd = best["sizes"]["droite"]
        for sl in (False, True):
            for sr in (False, True):
                chk = _eval_U_counts(
                    variant,
                    pts,
                    drawn,
                    sb,
                    sg,
                    sd,
                    sl,
                    sr,
                    traversins=traversins,
                )
                if (
                    abs(chk["waste"] - chosen["waste"]) < 1e-9
                    and chk["cover"] == chosen["cover"]
                ):
                    best["shiftL"], best["shiftR"] = sl, sr
                    return best
    return best

def _draw_U_with_sizes(
    variant, t, tr, pts, sizes, drawn, shiftL, shiftR, traversins=None
):
    """
    Draw cushions with specific sizes for each part of a U‑shaped sofa.

    ``sizes`` should be a dict with keys ``"bas"``, ``"gauche"`` and
    ``"droite"`` giving the cushion size for the bottom, left and right,
    respectively. This version respects méridienne limits via ``By_`` and
    ``By4_`` when present and optional traversins.
    """
    F0x, F0y = pts["F0"]
    x_end = _u_variant_x_end(variant, pts)
    # bottom
    xs = F0x + (CUSHION_DEPTH if shiftL else 0)
    xe = x_end - (CUSHION_DEPTH if shiftR else 0)
    sb = sizes["bas"]
    nb = 0
    x = xs
    y = F0y
    while x + sb <= xe + 1e-6:
        poly = [
            (x, y),
            (x + sb, y),
            (x + sb, y + CUSHION_DEPTH),
            (x, y + CUSHION_DEPTH),
            (x, y),
        ]
        draw_polygon_cm(
            t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1
        )
        label_poly(t, tr, poly, f"{sb}", font=FONT_CUSHION)
        nb += 1
        x += sb

    # left branch
    y_end_L = pts.get("By_", pts["By"])[1]
    if traversins and "g" in traversins:
        y_end_L -= TRAVERSIN_THK
    yL0 = F0y + (
        0
        if (not drawn.get("D1", False) or shiftL)
        else CUSHION_DEPTH
    )
    sg = sizes["gauche"]
    ng = 0
    xg = F0x
    y_ = yL0
    while y_ + sg <= y_end_L + 1e-6:
        poly = [
            (xg, y_),
            (xg + CUSHION_DEPTH, y_),
            (xg + CUSHION_DEPTH, y_ + sg),
            (xg, y_ + sg),
            (xg, y_),
        ]
        draw_polygon_cm(
            t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1
        )
        label_poly(t, tr, poly, f"{sg}", font=FONT_CUSHION)
        ng += 1
        y_ += sg

    # right branch
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins and "d" in traversins:
        y_end_R -= TRAVERSIN_THK
    has_right = drawn.get("D4", False) or drawn.get("D5", False)
    yR0 = F0y + (
        0
        if (not has_right or shiftR)
        else CUSHION_DEPTH
    )
    sd = sizes["droite"]
    nd = 0
    x_col = pts["Bx"][0] if variant in ("v1", "v4") else pts["F02"][0]
    y_ = yR0
    while y_ + sd <= y_end_R + 1e-6:
        poly = [
            (x_col - CUSHION_DEPTH, y_),
            (x_col, y_),
            (x_col, y_ + sd),
            (x_col - CUSHION_DEPTH, y_ + sd),
            (x_col - CUSHION_DEPTH, y_),
        ]
        draw_polygon_cm(
            t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1
        )
        label_poly(t, tr, poly, f"{sd}", font=FONT_CUSHION)
        nd += 1
        y_ += sd

    return nb + ng + nd

# ----- Simple S1 -----
def _optimize_valise_simple(pts, rng, mer_side=None, mer_len=0, traversins=None):
    x0 = pts["B0"][0]; x1 = pts["Bx"][0]
    if mer_side == 'g' and mer_len>0:
        x0 = max(x0, pts.get("B0_m", (x0,0))[0])
    if mer_side == 'd' and mer_len>0:
        x1 = min(x1, pts.get("Bx_m", (x1,0))[0])
    if traversins:
        if "g" in traversins: x0 += TRAVERSIN_THK
        if "d" in traversins: x1 -= TRAVERSIN_THK

    best=None; r0,r1=rng
    for s in range(r0, r1+1):
        n0, w0 = _waste_and_count_1d(max(0, x1-x0), s)
        n1, w1 = _waste_and_count_1d(max(0, x1-(x0+CUSHION_DEPTH)), s)
        if w1 < w0 or (w1==w0 and n1>n0):
            n, waste, off = n1, w1, CUSHION_DEPTH
        else:
            n, waste, off = n0, w0, 0
        score=(waste, -n, -s)
        if (best is None) or (score < best["score"]):
            best={"score":score, "size":s, "offset":off, "count":n}
    return best

def _draw_simple_with_size(t,tr,pts,size,mer_side=None,mer_len=0, traversins=None):
    x0 = pts["B0"][0]; x1 = pts["Bx"][0]
    if mer_side == 'g' and mer_len>0:
        x0 = max(x0, pts.get("B0_m", (x0,0))[0])
    if mer_side == 'd' and mer_len>0:
        x1 = min(x1, pts.get("Bx_m", pts["Bx"])[0])
    if traversins:
        if "g" in traversins: x0 += TRAVERSIN_THK
        if "d" in traversins: x1 -= TRAVERSIN_THK

    n0, w0 = _waste_and_count_1d(max(0,x1-x0), size)
    n1, w1 = _waste_and_count_1d(max(0,x1-(x0+CUSHION_DEPTH)), size)
    off = CUSHION_DEPTH if (w1 < w0 or (w1==w0 and n1>n0)) else 0
    x = x0 + off; y = pts["B0"][1]; n=0
    while x + size <= x1 + 1e-6:
        poly=[(x,y),(x+size,y),(x+size,y+CUSHION_DEPTH),(x,y+CUSHION_DEPTH),(x,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        x+=size; n+=1
    return n

# =====================================================================
# =======================  LF (L avec angle fromage)  ==================
# =====================================================================
def compute_points_LF_variant(tx, ty, profondeur=DEPTH_STD,
                              dossier_left=True, dossier_bas=True,
                              acc_left=True, acc_bas=True,
                              meridienne_side=None, meridienne_len=0):
    A = profondeur + 20
    prof = profondeur
    pts = {}
    if dossier_left and dossier_bas:
        F0x, F0y = 10, 10
    elif (not dossier_left) and dossier_bas:
        F0x, F0y = 0, 10
    elif dossier_left and (not dossier_bas):
        F0x, F0y = 10, 0
    else:
        F0x, F0y = 0, 0

    pts["F0"]  = (F0x, F0y)
    pts["Fy"]  = (F0x, F0y + A)
    pts["Fx"]  = (F0x + A, F0y)
    pts["Fy2"] = (F0x + prof, F0y + A)
    pts["Fx2"] = (F0x + A, F0y + prof)

    top_y = ty - (ACCOUDOIR_THICK if acc_left else 0)
    pts["By"]  = (F0x, top_y)
    pts["By2"] = (F0x + prof, top_y)

    pts["D0"]  = (0, 0)
    pts["D0x"] = (F0x, 0)
    pts["D0y"] = (0, F0y)
    pts["Dy"]  = (0, F0y + A)
    pts["Dy2"] = (0, top_y)

    pts["Ay"]  = (0, ty)
    pts["Ay2"] = (F0x + prof, ty)
    pts["Ay_"] = (F0x, ty)

    banq_stop_x = tx - (ACCOUDOIR_THICK if acc_bas else 0)
    pts["Dx"]  = (F0x + A, 0)
    pts["Dx2"] = (banq_stop_x, 0)
    pts["Bx"]  = (banq_stop_x, F0y)
    pts["Bx2"] = (banq_stop_x, F0y + prof)

    pts["Ax"]  = (tx, 0)
    pts["Ax2"] = (tx, F0y + prof)
    pts["Ax_"] = (tx, F0y)

    if meridienne_side == 'b' and meridienne_len > 0:
        dx2_stop = min(banq_stop_x, tx - meridienne_len)
        pts["Dx2"] = (dx2_stop, 0)
        pts["Bx_"] = (tx - meridienne_len, F0y)

    if meridienne_side == 'g' and meridienne_len > 0:
        mer_y = max(F0y + A, top_y - meridienne_len); mer_y = min(mer_y, top_y)
        pts["By_"] = (F0x, mer_y)
        pts["Dy2"] = (0, min(top_y, mer_y))

    if dossier_left and not dossier_bas:
        pts["D0y"] = (0, 0)
    if dossier_bas and not dossier_left:
        pts["D0x"] = (0, 0)

    return pts

def _choose_cushion_size_auto(pts, tx, ty, meridienne_side=None, meridienne_len=0, traversins=None):
    xF, yF = pts["F0"]
    x_end = pts.get("Bx_", pts.get("Bx", (tx, yF)))[0]
    if meridienne_side == 'b' and meridienne_len > 0:
        x_end = min(x_end, tx - meridienne_len)
    y_start = yF + CUSHION_DEPTH
    y_end = pts.get("By_", pts.get("By", (xF, ty)))[1]
    if traversins:
        if "b" in traversins: x_end -= TRAVERSIN_THK
        if "g" in traversins: y_end -= TRAVERSIN_THK
    # Harmonise sur le critere "surface couverte" de _choose_cushion_size_auto_L :
    # maximiser nb*taille, tie-break dechet minimal puis plus grande taille,
    # en testant les 2 dispositions de coin (bas colle / gauche colle au coin).
    def _cnt(length, s):
        return int(length // s) if length > 0 else 0
    best_size, best_score = 65, (-1, 0.0, 0)
    for s in (65, 80, 90):
        lhA = max(0.0, x_end - xF); lvA = max(0.0, y_end - (yF + CUSHION_DEPTH))
        nA = _cnt(lhA, s) + _cnt(lvA, s)
        wA = (lhA % s if lhA > 0 else 0) + (lvA % s if lvA > 0 else 0)
        lhB = max(0.0, x_end - (xF + CUSHION_DEPTH)); lvB = max(0.0, y_end - yF)
        nB = _cnt(lhB, s) + _cnt(lvB, s)
        wB = (lhB % s if lhB > 0 else 0) + (lvB % s if lvB > 0 else 0)
        cover, waste = (nB * s, wB) if (nB * s, -wB) > (nA * s, -wA) else (nA * s, wA)
        score = (cover, -waste, s)
        if score > best_score:
            best_score, best_size = score, s
    return best_size

def draw_cousins_and_return_count(t, tr, pts, tx, ty, coussins, meridienne_side, meridienne_len, traversins=None):
    if isinstance(coussins, str) and coussins.strip().lower() == "auto":
        size = _choose_cushion_size_auto(pts, tx, ty, meridienne_side, meridienne_len, traversins=traversins)
    else:
        size = int(coussins)

    F0x, F0y = pts["F0"]
    x_end = pts.get("Bx_", pts.get("Bx", (tx, F0y)))[0]
    y_end = pts.get("By_", pts.get("By", (F0x, ty)))[1]
    if traversins:
        if "b" in traversins: x_end -= TRAVERSIN_THK
        if "g" in traversins: y_end -= TRAVERSIN_THK

    def count_bas(x_start, x_stop):
        L = max(0, x_stop - x_start)
        return int(L // size)
    def count_gauche(y_start, y_stop):
        L = max(0, y_stop - y_start)
        return int(L // size)

    # Compare orientation A vs B
    A_bas = count_bas(F0x, x_end); A_g = count_gauche(F0y + CUSHION_DEPTH, y_end)
    B_bas = count_bas(F0x + CUSHION_DEPTH, x_end); B_g = count_gauche(F0y, y_end)
    use_shift = (B_bas + B_g, -( (x_end-(F0x+CUSHION_DEPTH))%size + (y_end-F0y)%size )) > (A_bas + A_g, -((x_end-F0x)%size + (y_end-(F0y+CUSHION_DEPTH))%size))

    count = 0
    # bas
    y = F0y
    x_cur = F0x + (CUSHION_DEPTH if use_shift else 0)
    while x_cur + size <= x_end + 1e-6:
        poly = [(x_cur, y), (x_cur+size, y), (x_cur+size, y+CUSHION_DEPTH), (x_cur, y+CUSHION_DEPTH), (x_cur, y)]
        draw_polygon_cm(t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1)
        label_poly(t, tr, poly, f"{size}", font=FONT_CUSHION)
        x_cur += size; count += 1
    # gauche
    x = F0x
    y_cur = F0y + (0 if use_shift else CUSHION_DEPTH)
    while y_cur + size <= y_end + 1e-6:
        poly = [(x, y_cur), (x+CUSHION_DEPTH, y_cur), (x+CUSHION_DEPTH, y_cur+size), (x, y_cur+size), (x, y_cur)]
        draw_polygon_cm(t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1)
        label_poly(t, tr, poly, f"{size}", font=FONT_CUSHION)
        y_cur += size; count += 1

    return count, size

def build_polys_LF_variant(pts, tx, ty, profondeur=DEPTH_STD,
                           dossier_left=True, dossier_bas=True,
                           acc_left=True, acc_bas=True,
                           meridienne_side=None, meridienne_len=0):
    polys={"angle":[],"banquettes":[],"dossiers":[],"accoudoirs":[]}

    angle=[pts["F0"],pts["Fx"],pts["Fx2"],pts["Fy2"],pts["Fy"],pts["F0"]]
    polys["angle"].append(angle)

    ban_g=[pts["Fy"],pts["Fy2"],pts["By2"],pts["By"],pts["Fy"]]
    Lg=abs(pts["By"][1]-pts["Fy"][1])
    split_g = False
    if Lg>SPLIT_THRESHOLD:
        split_g = True
        mid_y=_split_mid_int(pts["Fy"][1],pts["By"][1])
        Fy_mid=(pts["Fy"][0],mid_y); Fy2_mid=(pts["Fy2"][0],mid_y)
        polys["banquettes"]+=[
            [pts["Fy"],pts["Fy2"],Fy2_mid,Fy_mid,pts["Fy"]],
            [Fy_mid,Fy2_mid,pts["By2"],pts["By"],Fy_mid]
        ]
    else:
        polys["banquettes"].append(ban_g)

    ban_b=[pts["Fx"],pts["Fx2"],pts["Bx2"],pts["Bx"],pts["Fx"]]
    Lb=abs(pts["Bx"][0]-pts["Fx"][0])
    split_b = False
    if Lb>SPLIT_THRESHOLD:
        split_b = True
        mid_x=_split_mid_int(pts["Fx"][0],pts["Bx"][0])
        Fx_mid=(mid_x,pts["Fx"][1]); Fx2_mid=(mid_x,pts["Fx2"][1])
        polys["banquettes"]+=[
            [pts["Fx"],pts["Fx2"],Fx2_mid,Fx_mid,pts["Fx"]],
            [Fx_mid,Fx2_mid,pts["Bx2"],pts["Bx"],Fx_mid]
        ]
    else:
        polys["banquettes"].append(ban_b)

    if dossier_left:
        # retour gauche (inchangé)
        dos_g_from=[pts["D0"],pts["D0x"],pts["F0"],pts["Fy"],pts["Dy"],pts["D0"]] if dossier_bas \
            else [pts["D0y"],pts["F0"],pts["Fy"],pts["Dy"],pts["D0y"]]
        polys["dossiers"].append(dos_g_from)
        # bande sur la banquette gauche : scindée si nécessaire
        x0, x1 = 0, pts["F0"][0]
        y0 = pts["Dy"][1]
        y1 = pts.get("By_", pts["By"])[1]
        seat_y0 = pts["Fy"][1]
        seat_y1 = pts["By"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
    if dossier_bas:
        # retour bas (inchangé)
        dos_b_from=[pts["D0x"],pts["Dx"],pts["Fx"],pts["F0"],pts["D0x"]] if dossier_left \
            else [pts["D0x"],pts["F0"],pts["Fx"],pts["Dx"],pts["D0x"]]
        polys["dossiers"].append(dos_b_from)
        # bande sur la banquette bas : scindée si nécessaire
        y0, y1 = 0, pts["F0"][1]
        x0 = pts["Dx"][0]
        x1 = pts.get("Bx_", pts["Bx"])[0]
        seat_x0 = pts["Fx"][0]
        seat_x1 = pts["Bx"][0]
        polys["dossiers"] += _build_dossier_horizontal_rects(x0, x1, y0, y1, seat_x0, seat_x1)

    if acc_left:
        acc_g=[pts["Dy2"],pts["Ay"],pts["Ay2"],pts["By2"],pts["Dy2"]] if dossier_left \
            else [pts["By"],pts["Ay_"],pts["Ay2"],pts["By2"],pts["By"]]
        polys["accoudoirs"].append(acc_g)
    if acc_bas:
        acc_b=[pts["Dx2"],pts["Ax"],pts["Ax2"],pts["Bx2"],pts["Dx2"]] if dossier_bas \
            else [pts["Bx"],pts["Ax_"],pts["Ax2"],pts["Bx2"],pts["Bx"]]
        polys["accoudoirs"].append(acc_b)

    polys["split_flags"]={"left":split_g,"bottom":split_b,"right":False}
    return polys

def render_LF_variant(tx, ty, profondeur=DEPTH_STD,
                      dossier_left=True, dossier_bas=True,
                      acc_left=True, acc_bas=True,
                      meridienne_side=None, meridienne_len=0,
                      coussins="auto",
                      traversins=None,
                      couleurs=None,
                      window_title="LF — variantes"):
    if meridienne_side == 'g' and acc_left:
        raise ValueError("Erreur: une méridienne gauche ne peut pas coexister avec un accoudoir gauche.")
    if meridienne_side == 'b' and acc_bas:
        raise ValueError("Erreur: une méridienne bas ne peut pas coexister avec un accoudoir bas.")

    trv = _parse_traversins_spec(traversins, allowed={"g","b"})
    legend_items = _resolve_and_apply_colors(couleurs)

    pts=compute_points_LF_variant(tx,ty,profondeur,dossier_left,dossier_bas,acc_left,acc_bas,meridienne_side,meridienne_len)
    polys=build_polys_LF_variant(pts,tx,ty,profondeur,dossier_left,dossier_bas,acc_left,acc_bas,meridienne_side,meridienne_len)
    _assert_banquettes_max_250(polys)

    screen=turtle.Screen(); screen.setup(WIN_W,WIN_H)
    screen.title(f"{window_title} — {tx}x{ty} cm — prof={profondeur} — méridienne {meridienne_side or '-'}={meridienne_len} — coussins={coussins}")
    t=turtle.Turtle(visible=False); t.speed(0); screen.tracer(False)
    tr=WorldToScreen(tx,ty,WIN_W,WIN_H,PAD_PX,ZOOM)

    # (Quadrillage et repères supprimés)

    for poly in polys["dossiers"]:   draw_polygon_cm(t,tr,poly,fill=COLOR_DOSSIER)
    for poly in polys["banquettes"]: draw_polygon_cm(t,tr,poly,fill=COLOR_ASSISE)
    for poly in polys["accoudoirs"]: draw_polygon_cm(t,tr,poly,fill=COLOR_ACC)
    for poly in polys["angle"]:      draw_polygon_cm(t,tr,poly,fill=COLOR_ASSISE)

    # Traversins (visuel) + comptage
    n_traversins = _draw_traversins_L_like(t, tr, pts, profondeur, trv)

    draw_double_arrow_vertical_cm(t,tr,-25,0,ty,f"{ty} cm")
    draw_double_arrow_horizontal_cm(t,tr,-25,0,tx,f"{tx} cm")

    banquette_sizes = []
    if polys["angle"]:
        side = int(round(pts["Fy"][1] - pts["F0"][1]))
        # Écrire les dimensions d'angle sur deux lignes et centrer dans le carré d'angle
        # Pour l'angle, on affiche la première dimension sans unité suivie d'un « x » et la seconde avec « cm »
        label_poly(t, tr, polys["angle"][0], f"{side}x\n{side} cm")
    # Afficher les dimensions des banquettes en les décalant légèrement lorsqu'elles sont verticales
    for poly in polys["banquettes"]:
        L, P = banquette_dims(poly)
        banquette_sizes.append((L, P))
        # Afficher la première dimension sans unité suivie d'un « x », la seconde avec « cm »
        text = f"{L}x\n{P} cm"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Si la banquette est plus haute que large, décaler le texte vers la droite pour l'éloigner des coussins
        # Réduction de 3 cm : offset moindre pour un positionnement plus proche des coussins
        if bb_h >= bb_w:
            label_poly_offset_cm(t, tr, poly, text, dx_cm=CUSHION_DEPTH + 7, dy_cm=0.0)
        else:
            label_poly(t, tr, poly, text)
    # Annoter dossiers et accoudoirs avec leurs épaisseurs (« 10cm » pour le dossier le plus bas
    # et « 15cm » pour chaque accoudoir)
    _label_backrests_armrests(t, tr, polys)

    # ===== COUSSINS =====
    spec = _parse_coussins_spec(coussins)
    # Compteurs pour le nombre de coussins par taille pour le rapport console
    nb_coussins_65 = 0
    nb_coussins_80 = 0
    nb_coussins_90 = 0
    nb_coussins_valise = 0
    if spec["mode"] == "auto":
        cushions_count, chosen_size = draw_cousins_and_return_count(t,tr,pts,tx,ty,"auto",meridienne_side,meridienne_len,traversins=trv)
        total_line = f"{coussins} → {cushions_count} × {chosen_size} cm"
        # Mise à jour des compteurs pour le mode automatique
        if chosen_size == 65:
            nb_coussins_65 = cushions_count
        elif chosen_size == 80:
            nb_coussins_80 = cushions_count
        elif chosen_size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    elif spec["mode"] == "80-90":
        best = _optimize_80_90_L_like(pts, x_end_key="Bx", y_end_key="By", traversins=trv)
        if not best:
            raise ValueError('Aucune configuration "80-90" valide pour LF.')
        sizes = best["sizes"]
        shift_bas = best["shift_bas"]
        cushions_count, sb, sg = _draw_L_like_with_sizes(t, tr, pts, sizes, shift_bas, x_end_key="Bx", y_end_key="By", traversins=trv)
        total_line = _format_valise_counts_console({"bas": sb, "gauche": sg}, best.get("counts", best.get("eval", {}).get("counts")), cushions_count,)
        # Mise à jour des compteurs par taille en fonction des counts et tailles par côté
        counts_dict = best.get("counts", best.get("eval", {}).get("counts"))
        for side, size_val in sizes.items():
            count = counts_dict.get(side, 0)
            if not count:
                continue
            if size_val == 65:
                nb_coussins_65 += count
            elif size_val == 80:
                nb_coussins_80 += count
            elif size_val == 90:
                nb_coussins_90 += count
            else:
                nb_coussins_valise += count
    elif spec["mode"] == "fixed":
        cushions_count, chosen_size = draw_cousins_and_return_count(t,tr,pts,tx,ty,int(spec["fixed"]),meridienne_side,meridienne_len,traversins=trv)
        total_line = f"{coussins} → {cushions_count} × {chosen_size} cm"
        # Mise à jour des compteurs pour le mode fixe
        if chosen_size == 65:
            nb_coussins_65 = cushions_count
        elif chosen_size == 80:
            nb_coussins_80 = cushions_count
        elif chosen_size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    else:
        best = _optimize_valise_L_like(pts, spec["range"], spec["same"], x_end_key="Bx", y_end_key="By", traversins=trv)
        if not best:
            raise ValueError("Aucune configuration valise valide pour LF.")
        sizes = best["sizes"]; shift = best["shift_bas"]
        n, sb, sg = _draw_L_like_with_sizes(t, tr, pts, sizes, shift, x_end_key="Bx", y_end_key="By", traversins=trv)
        cushions_count = n
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # En mode valise, tous les coussins sont considérés comme des coussins valises
        nb_coussins_valise = cushions_count

    # Légende (couleurs)
    draw_legend(t, tr, tx, ty, items=legend_items, pos="top-right")

    screen.tracer(True); t.hideturtle()
    add_split = int(polys["split_flags"]["left"] and dossier_left) + int(polys["split_flags"]["bottom"] and dossier_bas)
    A = profondeur + 20
    print("=== Rapport canapé (LF) ===")
    print(f"Dimensions : {tx}×{ty} cm — profondeur : {profondeur} cm")
    print(f"Banquettes : {len(polys['banquettes'])} → {banquette_sizes}")
    # Comptage pondéré des dossiers : <=110cm → 0.5, >110cm → 1
    dossiers_count = _compute_dossiers_count(polys)
    # Formater le nombre de dossiers en évitant les décimales inutiles
    dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    print(f"Dossiers : {dossiers_str} (+{add_split} via scission) | Accoudoirs : {len(polys['accoudoirs'])}")
    print(f"Banquettes d’angle : 1")
    print(f"Angles : 1 × {A}×{A} cm")
    # Mise à jour de l’affichage des traversins pour refléter la nouvelle dimension 70×20 cm
    print(f"Traversins : {n_traversins} × 70x20")
    print(f"Coussins : {total_line}")
    # Détail issu des données pour le rapport console
    nb_banquettes = len(polys["banquettes"])
    nb_banquettes_angle = len(polys["angle"])
    nb_accoudoirs = len(polys["accoudoirs"])
    # Utiliser la représentation formatée pour le nombre de dossiers
    nb_dossiers_str = dossiers_str
    print()
    print("À partir des données console :")
    print(f"Dimensions : {tx}×{ty} cm — profondeur : {profondeur} cm (A={A})")
    print(f"Nombre de banquettes : {nb_banquettes}")
    print(f"Nombre de banquette d’angle : {nb_banquettes_angle}")
    print(f"Nombre de dossiers : {nb_dossiers_str}")
    print(f"Nombre d’accoudoir : {nb_accoudoirs}")
    # Afficher aussi les dimensions des accoudoirs par côté (gauche, bas, droite)
    _print_accoudoirs_dimensions(polys)
    # Impression détaillée des dossiers pour la variante LF.
    # On utilise des étiquettes de banquettes et leurs longueurs pour
    # déterminer les longueurs de mousse.  L'angle est carré (profondeur + 20).
    _banquette_labels = _compute_banquette_labels(polys)
    # angle_sizes est la longueur du côté de l'angle.  S'il n'y a pas
    # explicitement d'angle enregistré, on utilisera profondeur + 20.
    angle_sizes = []
    if polys.get("angle"):
        try:
            L_angle, P_angle = banquette_dims(polys["angle"][0])
            angle_sizes.append(int(round(L_angle)))
        except Exception:
            angle_sizes.append(int(profondeur) + 20)
    # Appel de la fonction dédiée au LF pour l'affichage des dossiers
    _print_dossiers_dimensions_LF(
        _banquette_labels,
        banquette_sizes,
        angle_sizes,
        profondeur,
        dossier_left,
        dossier_bas,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )
    # Dimensions des mousses pour chaque banquette droite
    # Étiquetage des banquettes en tenant compte des scissions : les
    # morceaux appartenant à une même branche partagent le même numéro avec
    # suffixe "-bis" pour le second morceau.  Voir _compute_banquette_labels.
    _banquette_labels = _compute_banquette_labels(polys)
    for label, (L_b, P_b) in zip(_banquette_labels, banquette_sizes):
        print(f"Dimension mousse {label} : {L_b}, {P_b}")
    # Dimensions des mousses d’angle
    for i, poly_angle in enumerate(polys["angle"], start=1):
        try:
            L_angle, P_angle = banquette_dims(poly_angle)
            print(f"Dimension mousse angle {i} : {L_angle}, {P_angle}")
        except Exception:
            continue
    # Répartition des coussins par catégorie
    print(f"Nombre de coussins 65cm : {nb_coussins_65}")
    print(f"Nombre de coussins 80cm : {nb_coussins_80}")
    print(f"Nombre de coussins 90cm : {nb_coussins_90}")
    print(f"Nombre de coussins valises total : {nb_coussins_valise}")
    print(f"Nombre de traversin : {n_traversins}")
    turtle.done()

# =====================================================================
# ========================  U2f (2 angles fromage)  ====================
# =====================================================================
def compute_points_U2f(tx, ty_left, tz_right, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True, dossier_right=True,
                       acc_left=True, acc_bas=True, acc_right=True,
                       meridienne_side=None, meridienne_len=0):
    A = profondeur + 20
    pts = {}
    # Offsets depend on presence of left and bottom backrests (10 cm if present, 0 otherwise)
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas else 0
    pts["D0"] = (0, 0)
    pts["D0x"] = (F0x, 0)
    pts["D0y"] = (0, F0y)
    pts["F0"] = (F0x, F0y)
    # Base of the left branch: height A above F0y
    pts["Fy"]  = (F0x,      F0y + A)
    pts["Fy2"] = (F0x+profondeur, F0y + A)
    # Start of the bottom run (between left and right branches)
    pts["Fx"]  = (F0x + A,  F0y)
    pts["Fx2"] = (F0x + A,  F0y + profondeur)

    top_y_L = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    # Left branch vertical points: align with F0y and F0x when there is no backrest
    pts["Dy"]  = (0, F0y + A)
    pts["Dy2"] = (0, top_y_L)
    pts["By"]  = (F0x, top_y_L)
    pts["By2"] = (F0x + profondeur, top_y_L)
    # Armrest end and alignment for the left branch
    pts["Ay"]  = (0, ty_left)
    pts["Ay2"] = (F0x + profondeur, ty_left)
    pts["Ay_"] = (F0x, ty_left)

    # Determine the interior end of the bottom run: subtract 10 cm only if a right backrest exists
    F02x = tx - (10 if dossier_right else 0)
    # Left branch end of bottom run occurs A cm before F02x
    BxL = F02x - A
    # Points for the bottom and right branches
    pts["Dx"]  = (F0x + A, 0)
    pts["Dx2"] = (BxL,     0)
    pts["Bx"]  = (BxL,     F0y)
    pts["Bx2"] = (BxL,     F0y + profondeur)

    pts["F02"] = (F02x, F0y)
    pts["Fy4"] = (F02x, F0y + A)
    pts["Fy3"] = (F02x - profondeur, F0y + A)
    top_y_R = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    pts["By3"]=(pts["Fy3"][0], top_y_R); pts["By4"]=(F02x, top_y_R)
    pts["D02"] = (tx, 0)
    # D02y starts at the same height as the base of the sofa (F0y)
    pts["D02y"] = (tx, F0y)
    # Right branch vertical segments align with F0y + A
    pts["Dy_r"] = (tx, F0y + A)
    pts["Dy2_r"] = (tx, top_y_R)
    # Armrest points (unchanged except for left/backrest offset at right)
    pts["Ax"]    = (pts["By3"][0], tz_right)
    pts["Ax2"]   = (tx, tz_right)
    # Adjust Ax_par depending on right backrest presence (subtract 10 cm only if dossier_right)
    pts["Ax_par"] = (tx - (10 if dossier_right else 0), tz_right)

    if meridienne_side == 'g' and meridienne_len > 0:
        mer_y_L = max(10 + A, ty_left - meridienne_len); mer_y_L = min(mer_y_L, top_y_L)
        pts["By_"]=(pts["By"][0], mer_y_L); pts["By2_"]=(pts["By2"][0], mer_y_L)
        pts["Dy2"]=(0, mer_y_L)
    if meridienne_side == 'd' and meridienne_len > 0:
        mer_y_R = max(10 + A, tz_right - meridienne_len); mer_y_R = min(mer_y_R, top_y_R)
        pts["By4_"]=(pts["By4"][0], mer_y_R); pts["Dy2_r"]=(tx, mer_y_R)

    pts["_ty_canvas"] = max(ty_left, tz_right)
    return pts

def build_polys_U2f(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                    dossier_left=True, dossier_bas=True, dossier_right=True,
                    acc_left=True, acc_bas=True, acc_right=True):
    polys = {"angles": [], "banquettes": [], "dossiers": [], "accoudoirs": []}
    # U2F — couture overlays for bottom angle seams (drawn after all other dossiers)
    angle_seams = []

    angle_L = [pts["F0"], pts["Fx"], pts["Fx2"], pts["Fy2"], pts["Fy"], pts["F0"]]
    polys["angles"].append(angle_L)
    angle_R = [pts["Bx2"], pts["Bx"], pts["F02"], pts["Fy4"], pts["Fy3"], pts["Bx2"]]
    polys["angles"].append(angle_R)

    # G
    ban_g = [pts["Fy"], pts["Fy2"], pts["By2"], pts["By"], pts["Fy"]]
    Lg = abs(pts["By"][1] - pts["Fy"][1])
    split_g = False
    if Lg > SPLIT_THRESHOLD:
        split_g = True
        mid_y = _split_mid_int(pts["Fy"][1], pts["By"][1])
        Fy_mid  = (pts["Fy"][0],  mid_y); Fy2_mid = (pts["Fy2"][0], mid_y)
        polys["banquettes"] += [[pts["Fy"],pts["Fy2"],Fy2_mid,Fy_mid,pts["Fy"]],
                                [Fy_mid,Fy2_mid,pts["By2"],pts["By"],Fy_mid]]
    else:
        polys["banquettes"].append(ban_g)

    # Bas
    ban_b = [pts["Fx"], pts["Fx2"], pts["Bx2"], pts["Bx"], pts["Fx"]]
    Lb = abs(pts["Bx"][0] - pts["Fx"][0])
    split_b = False
    if Lb > SPLIT_THRESHOLD:
        split_b = True
        mid_x = _split_mid_int(pts["Fx"][0], pts["Bx"][0])
        Fx_mid  = (mid_x, pts["Fx"][1]); Fx2_mid = (mid_x, pts["Fx2"][1])
        polys["banquettes"] += [[pts["Fx"],pts["Fx2"],Fx2_mid,Fx_mid,pts["Fx"]],
                                [Fx_mid,Fx2_mid,pts["Bx2"],pts["Bx"],Fx_mid]]
    else:
        polys["banquettes"].append(ban_b)

    # Droite
    ban_r = [pts["Fy3"], pts["By3"], pts["By4"], pts["Fy4"], pts["Fy3"]]
    Lr = abs(pts["By4"][1] - pts["Fy4"][1])
    split_r = False
    if Lr > SPLIT_THRESHOLD:
        split_r = True
        mid_y = _split_mid_int(pts["Fy4"][1], pts["By4"][1])
        Fy3_mid = (pts["Fy3"][0], mid_y); Fy4_mid = (pts["Fy4"][0], mid_y)
        polys["banquettes"] += [[pts["Fy3"],Fy3_mid,Fy4_mid,pts["Fy4"],pts["Fy3"]],
                                [Fy3_mid,pts["By3"],pts["By4"],Fy4_mid,Fy3_mid]]
    else:
        polys["banquettes"].append(ban_r)

    if dossier_left:
        # retour gauche : dépend de la présence du dossier bas
        if dossier_bas:
            # avec dossier bas : le retour inclut les 10 cm inférieurs
            polys["dossiers"].append([pts["D0"], pts["D0x"], pts["F0"], pts["Fy"], pts["Dy"], pts["D0"]])
        else:
            # sans dossier bas : on démarre à la hauteur de l'assise (10 cm)
            polys["dossiers"].append([pts["D0y"], pts["F0"], pts["Fy"], pts["Dy"], pts["D0y"]])
        # bande sur la banquette gauche : scindée si nécessaire
        x0, x1 = 0, pts["F0"][0]
        y0 = pts["Dy"][1]
        y1 = pts.get("By_", pts["By"])[1]
        seat_y0 = pts["Fy"][1]
        seat_y1 = pts["By"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
    # --- Dossiers bas : suivre la scission de la banquette du bas ---
    if dossier_bas:
        F0x, F0y = pts["F0"]
        F02x     = pts["F02"][0]  # fin intérieure côté droit
        # longueur de l'assise centrale (entre Fx et Bx)
        Lb = abs(pts["Bx"][0] - pts["Fx"][0])
        if Lb > SPLIT_THRESHOLD:
            mid_x = _split_mid_int(pts["Fx"][0], pts["Bx"][0])
            polys["dossiers"] += [
                _rectU(F0x, 0, mid_x, F0y),
                _rectU(mid_x, 0, F02x, F0y),
            ]
        else:
            polys["dossiers"].append(_rectU(F0x, 0, F02x, F0y))
    if dossier_right:
        # retour droit (dossier 6)
        if dossier_bas:
            # avec dossier bas : le retour inclut les 10 cm inférieurs
            F02x = pts["F02"][0]
            polys["dossiers"].append(_rectU(F02x, 0, pts["D02"][0], pts["Dy_r"][1]))
        else:
            # sans dossier bas : on démarre à la hauteur de l'assise (10 cm)
            polys["dossiers"].append([pts["D02y"], pts["F02"], pts["Fy4"], pts["Dy_r"], pts["D02y"]])
        # bande sur la banquette droite : scindée si nécessaire
        x0, x1 = pts["F02"][0], tx
        y0 = pts["Fy4"][1]
        y1 = pts.get("By4_", pts["By4"])[1]
        seat_y0 = pts["Fy4"][1]
        seat_y1 = pts["By4"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)

    if acc_left and dossier_left:
        polys["accoudoirs"].append([pts["Dy2"], pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"]])
    elif acc_left and not dossier_left:
        polys["accoudoirs"].append([pts["By"], pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"]])

    if acc_right and dossier_right:
        polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], pts["Dy2_r"], pts["By3"]])
    elif acc_right and not dossier_right:
        polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts.get("Ax_par", (tx-10, max(ty_left, tz_right))), pts["By4"], pts["By3"]])

    polys["split_flags"]={"left":split_g,"bottom":split_b,"right":split_r}
    # ------------------------------------------------------------
    # U2F — Overlays des coutures d’angle bas (toujours au-dessus de D3)
    # ------------------------------------------------------------
    # Ajoute deux fines bandes verticales sur les arêtes internes des angles
    # pour rendre visible la délimitation des dossiers d'angle bas.
    if dossier_bas:
        # Épaisseur visuelle de la couture : ~2% de la hauteur du dossier bas, bornée
        F0y_local = pts["F0"][1]
        seam = max(0.2, min(0.8, F0y_local * 0.02))
        # Angle gauche (D2) : trait vertical centré entre Fx.x et Dx.x
        # On trace cette couture dès qu'il y a un dossier bas, même si dossier_left est False.
        x_left_candidates = []
        if "Fx" in pts:
            x_left_candidates.append(pts["Fx"][0])
        if "Dx" in pts:
            x_left_candidates.append(pts["Dx"][0])
        if x_left_candidates:
            if len(x_left_candidates) > 1:
                x = 0.5 * (x_left_candidates[0] + x_left_candidates[1])
            else:
                x = x_left_candidates[0]
            angle_seams.append(_rectU(x - seam/2, 0, x + seam/2, F0y_local))
        # Angle droit (D4/D5) : trait vertical centré sur l'arête Dx2–Bx
        # On trace cette couture dès qu'il y a un dossier bas, même si dossier_right est False.
        x_right_candidates = []
        # Utiliser Dx2 et Bx pour la couture droite (médiane robuste si les deux existent)
        if "Dx2" in pts:
            x_right_candidates.append(pts["Dx2"][0])
        if "Bx" in pts:
            x_right_candidates.append(pts["Bx"][0])
        if x_right_candidates:
            if len(x_right_candidates) > 1:
                xr = 0.5 * (x_right_candidates[0] + x_right_candidates[1])
            else:
                xr = x_right_candidates[0]
            angle_seams.append(_rectU(xr - seam/2, 0, xr + seam/2, F0y_local))
    # Flusher les coutures en dernier pour garantir leur visibilité
    if angle_seams:
        polys["dossiers"] += angle_seams
    return polys

def _draw_cushions_U2f_optimized_wrapper(t, tr, pts, size, traversins=None):
    return _draw_cushions_U2f_optimized(t, tr, pts, size, traversins=traversins)

# ----------------------------------------------------------------------------
# Compatibilité : certains appels historiques utilisent une orthographe
# francisée ("coussins" au lieu de "cushions").  Afin d'éviter une
# ``NameError`` lorsque ces noms sont invoqués, on crée un alias.
_draw_coussins_U2f_optimized_wrapper = _draw_cushions_U2f_optimized_wrapper

def render_U2f_variant(tx, ty_left, tz_right, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True, dossier_right=True,
                       acc_left=True, acc_bas=True, acc_right=True,
                       meridienne_side=None, meridienne_len=0,
                       coussins="auto",
                       traversins=None,
                       couleurs=None,
                       window_title="U2F — variantes",
                       variant=None):
    """
    Rendu d’un canapé en U avec deux angles (U2F).  Les canapés U2F ne disposent
    d’aucune variante (comme v1, v2, etc.), mais un paramètre ``variant`` est
    accepté pour compatibilité et ignoré.  Toutes les autres options
    déterminent la géométrie, la présence d’accoudoirs/dossiers, la méridienne
    et l’optimisation des coussins.

    Paramètres
    ----------
    tx, ty_left, tz_right : numérique
        Dimensions des trois côtés (bas, gauche, droite) en centimètres.
    profondeur : int, optionnel
        Profondeur d’assise en cm (défaut : DEPTH_STD).
    dossier_left, dossier_bas, dossier_right : bool, optionnel
        Présence des dossiers à gauche, en bas et à droite.
    acc_left, acc_bas, acc_right : bool, optionnel
        Présence des accoudoirs à gauche, en bas et à droite.
    meridienne_side : str ou None
        'g' pour gauche ou 'd' pour droite ; une méridienne ne peut pas coexister
        avec un accoudoir du même côté.  Valeur par défaut : None.
    meridienne_len : int, optionnel
        Longueur de la méridienne en cm.  Ignoré si ``meridienne_side`` est None.
    coussins : str, optionnel
        Mode d’optimisation des coussins.
    traversins : str ou None, optionnel
        Configuration des traversins.
    couleurs : dict ou None, optionnel
        Substitution de la palette de couleurs.
    window_title : str, optionnel
        Titre de la fenêtre matplotlib.
    variant : any, optionnel
        Paramètre ignoré destiné à maintenir la compatibilité avec des appels
        qui fournissent à tort un variant pour U2F.  Il n’a aucun effet.
    """
    # Ignorer le paramètre variant ; aucune variante n’existe pour U2F
    _ = variant
    if meridienne_side == 'g' and acc_left:
        raise ValueError("Erreur: une méridienne gauche ne peut pas coexister avec un accoudoir gauche.")
    if meridienne_side == 'd' and acc_right:
        raise ValueError("Erreur: une méridienne droite ne peut pas coexister avec un accoudoir droit.")

    trv = _parse_traversins_spec(traversins, allowed={"g","d"})
    legend_items = _resolve_and_apply_colors(couleurs)

    pts = compute_points_U2f(tx, ty_left, tz_right, profondeur,
                             dossier_left, dossier_bas, dossier_right,
                             acc_left, acc_bas, acc_right,
                             meridienne_side, meridienne_len)
    polys = build_polys_U2f(pts, tx, ty_left, tz_right, profondeur,
                            dossier_left, dossier_bas, dossier_right,
                            acc_left, acc_bas, acc_right)
    _assert_banquettes_max_250(polys)

    ty_canvas = pts["_ty_canvas"]
    screen = turtle.Screen(); screen.setup(WIN_W, WIN_H)
    screen.title(f"{window_title} — tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur}")
    t = turtle.Turtle(visible=False); t.speed(0); screen.tracer(False)
    tr = WorldToScreen(tx, ty_canvas, WIN_W, WIN_H, PAD_PX, ZOOM)

    # (Quadrillage et repères supprimés)

    for poly in polys["dossiers"]:   draw_polygon_cm(t, tr, poly, fill=COLOR_DOSSIER)
    for poly in polys["banquettes"]: draw_polygon_cm(t, tr, poly, fill=COLOR_ASSISE)
    for poly in polys["accoudoirs"]: draw_polygon_cm(t, tr, poly, fill=COLOR_ACC)
    for poly in polys["angles"]:     draw_polygon_cm(t, tr, poly, fill=COLOR_ASSISE)

    # Traversins (visuel) + comptage
    n_traversins = _draw_traversins_U_side_F02(t, tr, pts, profondeur, trv)

    draw_double_arrow_vertical_cm(t, tr, -25,    0, ty_left,  f"{ty_left} cm")
    draw_double_arrow_vertical_cm(t, tr,  tx+25, 0, tz_right, f"{tz_right} cm")
    draw_double_arrow_horizontal_cm(t, tr, -25,  0, tx, f"{tx} cm")

    A = profondeur + 20
    for poly in polys["angles"]:
        # Écrire les dimensions d’angle sur deux lignes, première ligne sans unité suivie d’un « x »
        label_poly(t, tr, poly, f"{A}x\n{A} cm")

    banquette_sizes = []
    for poly in polys["banquettes"]:
        L, P = banquette_dims(poly)
        banquette_sizes.append((L, P))
        # Affichage de la dimension principale sans unité suivie d'un « x », et de la profondeur avec « cm »
        text = f"{L}x\n{P} cm"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Décaler horizontalement si la banquette est plus haute que large
        if bb_h >= bb_w:
            cx = sum(xs) / len(xs)
            # Réduire les offsets : 3 cm en moins sur les branches verticales
            # Branche gauche : CUSHION_DEPTH+7 (ex: 22 cm). Branche droite : -(CUSHION_DEPTH-8) (ex: -7 cm).
            dx = (CUSHION_DEPTH + 7) if cx < tx / 2.0 else -(CUSHION_DEPTH - 8)
            label_poly_offset_cm(t, tr, poly, text, dx_cm=dx, dy_cm=0.0)
        else:
            label_poly(t, tr, poly, text)

    # Après avoir étiqueté les banquettes, annoter dossiers et accoudoirs
    # avec leurs épaisseurs (« 10cm » pour le dossier le plus bas et « 15cm » pour chaque accoudoir)
    _label_backrests_armrests(t, tr, polys)

    # ===== COUSSINS =====
    spec = _parse_coussins_spec(coussins)
    # Préparer des compteurs pour le rapport console. Ces compteurs serviront
    # à ventiler le nombre de coussins selon les tailles 65 cm, 80 cm,
    # 90 cm et valise (autres tailles).  Ils seront alimentés dans
    # chaque branche ci‑dessous selon la taille finalement retenue.
    nb_coussins_65 = 0
    nb_coussins_80 = 0
    nb_coussins_90 = 0
    nb_coussins_valise = 0
    if spec["mode"] == "auto":
        # ancien auto (65,80,90) : une seule taille pour tout le canapé
        F0x, F0y = pts["F0"]
        F02x = pts["F02"][0]
        y_end_L = pts.get("By_", pts["By"])[1]
        y_end_R = pts.get("By4_", pts["By4"])[1]
        if trv:
            if "g" in trv:
                y_end_L -= TRAVERSIN_THK
            if "d" in trv:
                y_end_R -= TRAVERSIN_THK
        best_size = 65
        best_score = (-1, 0.0, 0)
        for s in (65, 80, 90):
            usable_h = max(0, F02x - F0x)
            usable_v_L = max(0, y_end_L - (F0y + CUSHION_DEPTH))
            usable_v_R = max(0, y_end_R - (F0y + CUSHION_DEPTH))
            n = ((int(usable_h // s) if usable_h > 0 else 0)
                 + (int(usable_v_L // s) if usable_v_L > 0 else 0)
                 + (int(usable_v_R // s) if usable_v_R > 0 else 0))
            cover = n * s
            waste = ((usable_h % s if usable_h > 0 else 0)
                     + (usable_v_L % s if usable_v_L > 0 else 0)
                     + (usable_v_R % s if usable_v_R > 0 else 0))
            score = (cover, -waste, s)
            if score > best_score:
                best_score, best_size = score, s
        size = best_size
        cushions_count = _draw_coussins_U2f_optimized_wrapper(
            t, tr, pts, size, traversins=trv
        )
        total_line = f"{coussins} → {cushions_count} × {size} cm"
        # Répartition des coussins par tailles pour le rapport.  En mode auto,
        # une seule taille est choisie pour tous les coussins.  On met à jour
        # le compteur correspondant.
        if size == 65:
            nb_coussins_65 = cushions_count
        elif size == 80:
            nb_coussins_80 = cushions_count
        elif size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    elif spec["mode"] == "80-90":
        best = _optimize_80_90_U2f(pts, traversins=trv)
        if not best:
            raise ValueError('Aucune configuration "80-90" valide pour U2f.')
        sizes = best["sizes"]
        shiftL = best.get("shiftL", False)
        shiftR = best.get("shiftR", False)
        cushions_count = _draw_U2f_with_sizes(
            t,
            tr,
            pts,
            sizes,
            shiftL,
            shiftR,
            traversins=trv,
        )
        sb, sg, sd = sizes["bas"], sizes["gauche"], sizes["droite"]
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg, "droite": sd},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # Répartition des coussins par tailles pour le rapport.  Dans la
        # configuration 80‑90, on dispose de trois tailles de coussins (bas,
        # gauche, droite) avec un nombre associé pour chaque côté.  On
        # récupère le dictionnaire des comptes pour répartir par taille.
        counts_dict = best.get("counts", best.get("eval", {}).get("counts"))
        if counts_dict:
            for side, size_val in [("bas", sb), ("gauche", sg), ("droite", sd)]:
                count = counts_dict.get(side, 0)
                if not count:
                    continue
                if size_val == 65:
                    nb_coussins_65 += count
                elif size_val == 80:
                    nb_coussins_80 += count
                elif size_val == 90:
                    nb_coussins_90 += count
                else:
                    nb_coussins_valise += count
    elif spec["mode"] == "fixed":
        size = int(spec["fixed"])
        cushions_count = _draw_coussins_U2f_optimized_wrapper(
            t, tr, pts, size, traversins=trv
        )
        total_line = f"{coussins} → {cushions_count} × {size} cm"
        # Répartition des coussins par tailles pour le rapport.  En mode
        # fixe, tous les coussins partagent une taille définie par
        # l’utilisateur.
        if size == 65:
            nb_coussins_65 = cushions_count
        elif size == 80:
            nb_coussins_80 = cushions_count
        elif size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    else:
        best = _optimize_valise_U2f(
            pts, spec["range"], spec["same"], traversins=trv
        )
        if not best:
            raise ValueError("Aucune configuration valise valide pour U2f.")
        sizes = best["sizes"]
        shiftL = best["shiftL"]
        shiftR = best["shiftR"]
        cushions_count = _draw_U2f_with_sizes(
            t,
            tr,
            pts,
            sizes,
            shiftL,
            shiftR,
            traversins=trv,
        )
        sb, sg, sd = sizes["bas"], sizes["gauche"], sizes["droite"]
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg, "droite": sd},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # En mode valise, toutes les tailles sont considérées comme des
        # coussins valise (autres tailles).  On attribue donc tout le
        # compte à ce compteur.
        nb_coussins_valise = cushions_count

    # Titre demandé + légende (U → légende en haut-centre)
    draw_title_center(t, tr, tx, ty_canvas, "Canapé en U avec deux angles")
    draw_legend(t, tr, tx, ty_canvas, items=legend_items, pos="top-center")

    screen.tracer(True); t.hideturtle()
    # Calcul du bonus de scission des dossiers
    dossier_bonus = int(polys["split_flags"].get("left", False) and dossier_left) + \
                    int(polys["split_flags"].get("bottom", False) and dossier_bas) + \
                    int(polys["split_flags"].get("right", False) and dossier_right)

    # Comptage pondéré des dossiers : <=110cm → 0.5, >110cm → 1
    dossiers_count = _compute_dossiers_count(polys)
    # Formater le nombre de dossiers en évitant les décimales inutiles
    dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    # Compteurs pour les autres éléments
    nb_banquettes = len(polys["banquettes"])
    nb_banquettes_angle = len(polys["angles"])
    nb_accoudoirs = len(polys["accoudoirs"])

    # Rapport de base (format historique)
    print("=== Rapport canapé U2f ===")
    print(f"Dimensions : tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur} (A={A})")
    print(f"Méridienne : {meridienne_side or '-'} ({meridienne_len} cm)")
    print(f"Banquettes : {nb_banquettes} → {banquette_sizes}")
    print(f"Dossiers : {dossiers_str} (+{dossier_bonus} via scission) | Accoudoirs : {nb_accoudoirs}")
    print(f"Banquettes d'angle : {nb_banquettes_angle}")
    print(f"Angles : {nb_banquettes_angle} × {A}×{A} cm")
    # Mise à jour de l’affichage des traversins pour refléter 70×20 cm
    print(f"Traversins : {n_traversins} × 70x20")
    print(f"Coussins : {total_line}")

    # ======= NOUVEAU BLOC "À partir des données console" =======
    print()
    print("À partir des données console :")
    print(f"Dimensions : tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur} (A={A})")
    print(f"Méridienne : {meridienne_side or '-'} ({meridienne_len} cm)")
    print(f"Nombre de banquettes : {nb_banquettes}")
    print(f"Nombre de banquette d’angle : {nb_banquettes_angle}")
    print(f"Nombre de dossiers : {dossiers_str}")
    print(f"Nombre d’accoudoir : {nb_accoudoirs}")
    # Afficher également les dimensions des accoudoirs
    _print_accoudoirs_dimensions(polys)
    # Calculer les étiquettes et imprimer les dimensions des dossiers spécifiquement
    # pour les canapés U2F en suivant le format demandé.  Les longueurs
    # d’assise sont récupérées via _compute_banquette_labels et
    # banquette_sizes.  Les longueurs des angles sont la première
    # dimension des polygones d’angle.
    _banquette_labels = _compute_banquette_labels(polys)
    _angle_sizes = []
    for _poly_angle in polys["angles"]:
        _L_angle, _P_angle = banquette_dims(_poly_angle)
        _angle_sizes.append(_L_angle)
    _print_dossiers_dimensions_U2f(
        _banquette_labels,
        banquette_sizes,
        _angle_sizes,
        dossier_left,
        dossier_bas,
        dossier_right,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )
    # Dimensions des mousses droites
    # Utiliser des étiquettes "n" et "n-bis" pour distinguer les scissions d'une même branche
    for label, (L, P) in zip(_banquette_labels, banquette_sizes):
        print(f"Dimension mousse {label} : {L}, {P}")
    # Dimensions des mousses d’angle
    for i, poly in enumerate(polys["angles"], start=1):
        L_angle, P_angle = banquette_dims(poly)
        print(f"Dimension mousse angle {i} : {L_angle}, {P_angle}")
    # Répartition des coussins par catégories
    print(f"Nombre de coussins 65cm : {nb_coussins_65}")
    print(f"Nombre de coussins 80cm : {nb_coussins_80}")
    print(f"Nombre de coussins 90cm : {nb_coussins_90}")
    print(f"Nombre de coussins valises total : {nb_coussins_valise}")
    print(f"Nombre de traversin : {n_traversins}")
    turtle.done()

# =====================================================================
# ===================  U1F (1 angle fromage) — v1..v4  =================
# =====================================================================
# (version validée + palette + légende U en haut-centre)

def _split_banquette_if_needed_U1F(poly):
    xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    x0,x1=min(xs),max(xs); y0,y1=min(ys),max(ys)
    w=x1-x0; h=y1-y0
    if w<=SPLIT_THRESHOLD and h<=SPLIT_THRESHOLD:
        return [poly], False
    res=[]
    split=True
    if w>=h and w>SPLIT_THRESHOLD:
        mx=_split_mid_int(x0,x1)
        left = [(x0,y0),(mx,y0),(mx,y1),(x0,y1),(x0,y0)]
        right=[(mx,y0),(x1,y0),(x1,y1),(mx,y1),(mx,y0)]
        res += [left,right]
    else:
        my=_split_mid_int(y0,y1)
        low =[(x0,y0),(x1,y0),(x1,my),(x0,my),(x0,y0)]
        high=[(x0,my),(x1,my),(x1,y1),(x0,y1),(x0,my)]
        res += [low,high]
    return res, split

def _common_offsets_u1f(profondeur, dossier_left, dossier_bas, dossier_right):
    A = profondeur + 20
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas  else 0
    return A, F0x, F0y

def _choose_cushion_size_auto_U1F(pts, traversins=None):
    F0x, F0y = pts["F0"]; F02x = pts["F02"][0]
    x_len = max(0, F02x - F0x)
    y_end_L = pts["By_cush"][1]
    y_end_R = pts["By4_cush"][1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK
    yL0 = F0y + CUSHION_DEPTH
    yR0 = F0y + CUSHION_DEPTH
    # Harmonise sur le critere "surface couverte" (cf. _choose_cushion_size_auto_L).
    best, score_best = 65, (-1, 0.0, 0)
    for s in (65,80,90):
        len_bas = x_len
        len_g   = max(0, y_end_L - yL0)
        len_d   = max(0, y_end_R - yR0)
        n = ((len_bas // s if len_bas > 0 else 0)
             + (len_g // s if len_g > 0 else 0)
             + (len_d // s if len_d > 0 else 0))
        cover = n * s
        waste = ((len_bas % s if len_bas > 0 else 0)
                 + (len_g % s if len_g > 0 else 0)
                 + (len_d % s if len_d > 0 else 0))
        sc = (cover, -waste, s)
        if sc > score_best: best, score_best = s, sc
    return best

def _draw_coussins_U1F(t, tr, pts, size, traversins=None):
    F0x, F0y = pts["F0"]; F02x = pts["F02"][0]
    y_end_L = pts["By_cush"][1]; y_end_R = pts["By4_cush"][1]
    if traversins:
        if "g" in traversins: y_end_L -= TRAVERSIN_THK
        if "d" in traversins: y_end_R -= TRAVERSIN_THK
    def cnt_h(x0,x1): return int(max(0,x1-x0)//size)
    def cnt_v(y0,y1): return int(max(0,y1-y0)//size)
    def score(sL,sR):
        xs = F0x + (CUSHION_DEPTH if sL else 0)
        xe = F02x - (CUSHION_DEPTH if sR else 0)
        bas = cnt_h(xs,xe)
        yL0 = F0y + (0 if sL else CUSHION_DEPTH)
        yR0 = F0y + (0 if sR else CUSHION_DEPTH)
        g = cnt_v(yL0,y_end_L); d = cnt_v(yR0,y_end_R)
        w = (max(0,xe-xs)%size) + (max(0,y_end_L-yL0)%size) + (max(0,y_end_R-yR0)%size)
        return (bas+g+d, -w), xs, xe, yL0, yR0
    candidates=[score(False,False),score(True,False),score(False,True),score(True,True)]
    _, xs, xe, yL0, yR0 = max(candidates, key=lambda s:s[0])

    count=0
    # BAS
    y = F0y; x = xs
    while x + size <= xe + 1e-6:
        poly=[(x,y),(x+size,y),(x+size,y+CUSHION_DEPTH),(x,y+CUSHION_DEPTH),(x,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        count+=1; x+=size
    # GAUCHE
    x = F0x; y = yL0
    while y + size <= y_end_L + 1e-6:
        poly=[(x,y),(x+CUSHION_DEPTH,y),(x+CUSHION_DEPTH,y+size),(x,y+size),(x,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        count+=1; y+=size
    # DROITE
    x = F02x; y = yR0
    while y + size <= y_end_R + 1e-6:
        poly=[(x-CUSHION_DEPTH,y),(x,y),(x,y+size),(x-CUSHION_DEPTH,y+size),(x-CUSHION_DEPTH,y)]
        draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
        label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
        count+=1; y+=size
    return count

def compute_points_U1F_v1(tx, ty_left, tz_right, profondeur=DEPTH_STD,
                          dossier_left=True, dossier_bas=True, dossier_right=True,
                          acc_left=True, acc_right=True,
                          meridienne_side=None, meridienne_len=0):
    if meridienne_side == 'g' and acc_left:  raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
    if meridienne_side == 'd' and acc_right: raise ValueError("Méridienne droite interdite avec accoudoir droit.")

    A, F0x, F0y = _common_offsets_u1f(profondeur, dossier_left, dossier_bas, dossier_right)
    pts={}
    pts["D0"]=(0,0); pts["D0x"]=(F0x,0); pts["D0y"]=(0,F0y); pts["F0"]=(F0x,F0y)

    # Gauche
    pts["Fy"]  = (F0x, F0y + A); pts["Fy2"]=(F0x+profondeur, F0y + A)
    pts["Fx"]  = (F0x + A, F0y); pts["Fx2"]=(F0x + A, F0y + profondeur); pts["Dx"]=(F0x + A, 0)

    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos  = (max(F0y + A, top_y_L_full - meridienne_len) if meridienne_side=='g' else top_y_L_full)
    pts["By"]=(F0x, top_y_L_full); pts["By2"]=(F0x+profondeur, top_y_L_full)
    pts["Dy"]=(0, F0y + A); pts["Dy2"]=(0, top_y_L_dos)
    pts["By_dL"]=(F0x, top_y_L_dos)   # stop dossier G avec méridienne G
    pts["Ay"]=(0, ty_left); pts["Ay2"]=(F0x+profondeur, ty_left); pts["Ay_"]=(F0x, ty_left)

    # Bas/droite
    D02x_x = tx - (10 if (dossier_right or dossier_bas) else 0)
    pts["D02x"]=(D02x_x,0); pts["F02"]=(D02x_x, F0y)
    Dx2_x = D02x_x - profondeur
    pts["Dx2"]=(Dx2_x,0); pts["Bx"]=(Dx2_x, F0y); pts["Bx2"]=(Dx2_x, F0y + profondeur)
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    top_y_R_dos  = (max(F0y + A, top_y_R_full - meridienne_len) if meridienne_side=='d' else top_y_R_full)
    pts["By3"]=(Dx2_x, top_y_R_full); pts["By4"]=(D02x_x, top_y_R_full); pts["By4_d"]=(D02x_x, top_y_R_dos)
    pts["D02"]=(tx,0); pts["D02y"]=(tx, F0y); pts["Dy3"]=(tx, top_y_R_dos)
    pts["Ax"]=(Dx2_x, tz_right); pts["Ax2"]=(tx, tz_right); pts["Ax_par"]=(D02x_x, tz_right)

    if not dossier_bas:
        pts["D0y"]=(0,0); pts["D02y"]=(tx,0)

    pts["By_cush"]=(pts["By"][0], min(pts["By"][1], pts["Dy2"][1]))
    pts["By4_cush"]=(pts["By4"][0], min(pts["By4"][1], pts["By4_d"][1]))

    pts["_A"]=A; pts["_ty_canvas"]=max(ty_left, tz_right)
    pts["_draw"]={
        "D1": bool(dossier_left), "D2": bool(dossier_left),
        "D3": bool(dossier_bas),  "D4": bool(dossier_bas), "D5": bool(dossier_bas),
        "D6": bool(dossier_right),
    }
    pts["_acc"]={"L":acc_left, "R":acc_right}
    return pts

def build_polys_U1F_v1(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True, dossier_right=True,
                       acc_left=True, acc_right=True):
    polys={"angle": [], "banquettes": [], "dossiers": [], "accoudoirs": []}
    d={"D1":dossier_left,"D2":dossier_left,"D3":dossier_bas,"D4":dossier_bas,"D5":dossier_bas,"D6":dossier_right}

    polys["angle"].append([pts["F0"], pts["Fx"], pts["Fx2"], pts["Fy2"], pts["Fy"], pts["F0"]])

    split_any=False
    for ban in (
        [pts["Fy"], pts["Fy2"], pts["By2"], pts["By"], pts["Fy"]],
        [pts["Fx2"], pts["Fx"], pts["Bx"], pts["Bx2"], pts["Fx2"]],
        [pts["Bx"], pts["F02"], pts["By4"], pts["By3"], pts["Bx"]],
    ):
        pieces, split = _split_banquette_if_needed_U1F(ban)
        polys["banquettes"] += pieces
        split_any = split_any or split

    if d["D1"]:
        # scinder D1 sur la banquette gauche si nécessaire
        x0, x1 = 0, pts["F0"][0]
        y0 = pts["Fy"][1]
        y1 = pts["By_dL"][1]
        seat_y0, seat_y1 = pts["Fy"][1], pts["By"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
    if d["D2"]: polys["dossiers"].append([pts["D0x"], pts["D0"], pts["Dy"], pts["Fy"], pts["D0x"]])
    # --- Dossiers bas : 1 ou 2 rectangles selon scission de l'assise ---
    if d["D3"] or d["D4"] or d["D5"]:
        F0x, F0y   = pts["F0"]
        xL_total   = F0x
        xR_total   = pts["F02"][0]                 # fin intérieure à droite
        Lb         = abs(pts["Bx"][0] - pts["Fx"][0])  # assise centrale
        if Lb > SPLIT_THRESHOLD:
            mid_x = _split_mid_int(pts["Fx"][0], pts["Bx"][0])
            polys["dossiers"] += [
                _rectU(xL_total, 0, mid_x,  F0y),
                _rectU(mid_x,    0, xR_total, F0y),
            ]
        else:
            polys["dossiers"].append(_rectU(xL_total, 0, xR_total, F0y))
    if d["D6"]:
        # scinder D6 (droit haut) si nécessaire
        x0, x1 = pts["D02x"][0], tx
        y0 = 0
        y1 = pts["By4_d"][1]
        seat_y0, seat_y1 = pts["F0"][1], pts["By4"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)

    if acc_left:
        if d["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])
    if acc_right:
        if d["D6"]:
            dy_top = pts.get("Dy3", None) or pts.get("Dy4", None)
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], dy_top, pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    # U1F v1 — délimitations verticales des dossiers bas :
    # - Dx–Fx  : jonction dossiers 3 et 4
    # - Dx2–Bx : jonction dossiers 4 et 5
    if dossier_bas:
        F0y_local = pts["F0"][1]
        seam = max(0.2, min(0.8, F0y_local * 0.02))
        # Jonction D3/D4 : trait centré entre Dx.x et Fx.x
        x_mid_candidates = []
        if "Dx" in pts:
            x_mid_candidates.append(pts["Dx"][0])
        if "Fx" in pts:
            x_mid_candidates.append(pts["Fx"][0])
        if x_mid_candidates:
            if len(x_mid_candidates) > 1:
                xm = 0.5 * (x_mid_candidates[0] + x_mid_candidates[1])
            else:
                xm = x_mid_candidates[0]
            polys["dossiers"].append(_rectU(xm - seam/2, 0, xm + seam/2, F0y_local))
        # Jonction D4/D5 : trait centré entre Dx2.x et Bx.x
        x_right_candidates = []
        if "Dx2" in pts:
            x_right_candidates.append(pts["Dx2"][0])
        if "Bx" in pts:
            x_right_candidates.append(pts["Bx"][0])
        if x_right_candidates:
            if len(x_right_candidates) > 1:
                xr = 0.5 * (x_right_candidates[0] + x_right_candidates[1])
            else:
                xr = x_right_candidates[0]
            polys["dossiers"].append(_rectU(xr - seam/2, 0, xr + seam/2, F0y_local))

    polys["split_flags"]={"any":split_any}
    return polys

def compute_points_U1F_v2(tx, ty_left, tz_right, profondeur=DEPTH_STD,
                          dossier_left=True, dossier_bas=True, dossier_right=True,
                          acc_left=True, acc_right=True,
                          meridienne_side=None, meridienne_len=0):
    if meridienne_side == 'g' and acc_left:  raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
    if meridienne_side == 'd' and acc_right: raise ValueError("Méridienne droite interdite avec accoudoir droit.")

    A, F0x, F0y = _common_offsets_u1f(profondeur, dossier_left, dossier_bas, dossier_right)
    pts={}
    pts["D0"]=(0,0); pts["D0x"]=(F0x,0); pts["D0y"]=(0,F0y); pts["F0"]=(F0x,F0y)

    # Gauche
    pts["Fy"]=(F0x, F0y + A); pts["Fy2"]=(F0x+profondeur, F0y + A)
    pts["Fx"]=(F0x + A, F0y); pts["Fx2"]=(F0x + A, F0y + profondeur); pts["Dx"]=(F0x + A, 0)

    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos  = (max(F0y + A, top_y_L_full - meridienne_len) if meridienne_side=='g' else top_y_L_full)
    pts["By"]=(F0x, top_y_L_full); pts["By2"]=(F0x+profondeur, top_y_L_full)
    pts["Dy"]=(0, F0y + A); pts["Dy2"]=(0, top_y_L_dos)
    pts["By_dL"]=(F0x, top_y_L_dos)
    pts["Ay"]=(0, ty_left); pts["Ay2"]=(F0x+profondeur, ty_left); pts["Ay_"]=(F0x, ty_left)

    # Droite interne F02 (dep. dossier_right)
    F02x = tx - (10 if dossier_right else 0)
    pts["F02"]=(F02x, F0y)
    # ajout alias D02x pour build_polys_U1F_v2
    pts["D02x"] = (F02x, 0)  # alias utilisé par build_polys_U1F_v2

    # Bas v2
    pts["Dx2"]=(F02x, 0); pts["Bx2"]=(F02x, F0y + profondeur)

    # Colonne droite (x = F02x - profondeur)
    col_x = F02x - profondeur
    pts["Fy3"]=(col_x, F0y + profondeur); pts["By3"]=(col_x, tz_right - (ACCOUDOIR_THICK if acc_right else 0))

    # Extrémité droite
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    top_y_R_dos  = (max(F0y + A, top_y_R_full - meridienne_len) if meridienne_side=='d' else top_y_R_full)
    pts["By4"]=(F02x, top_y_R_full); pts["By4_d"]=(F02x, top_y_R_dos)
    pts["D02"]=(tx,0); pts["D02y"]=(tx, F0y); pts["Dy3"]=(tx, F0y + profondeur); pts["Dy4"]=(tx, top_y_R_dos)
    pts["Ax"]=(col_x, tz_right); pts["Ax2"]=(tx, tz_right); pts["Ax_par"]=(F02x, tz_right)

    if not dossier_bas:
        pts["D0y"]=(0,0); pts["D02y"]=(tx,0)

    pts["By_cush"]=(pts["By"][0], min(pts["By"][1], pts["Dy2"][1]))
    pts["By4_cush"]=(pts["By4"][0], min(pts["By4"][1], pts["By4_d"][1]))

    pts["_A"]=A; pts["_ty_canvas"]=max(ty_left, tz_right)
    pts["_draw"]={
        "D1": bool(dossier_left), "D2": bool(dossier_left),
        "D3": bool(dossier_bas),  "D4": bool(dossier_bas), "D5": bool(dossier_bas),
        "D6": bool(dossier_right),
    }
    pts["_acc"]={"L":acc_left, "R":acc_right}
    return pts

def build_polys_U1F_v2(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True, dossier_right=True,
                       acc_left=True, acc_right=True):
    polys={"angle": [], "banquettes": [], "dossiers": [], "accoudoirs": []}
    d={"D1":dossier_left,"D2":dossier_left,"D3":dossier_bas,"D4":dossier_bas,"D5":dossier_bas,"D6":dossier_right}

    polys["angle"].append([pts["F0"], pts["Fx"], pts["Fx2"], pts["Fy2"], pts["Fy"], pts["F0"]])

    split_any=False
    for ban in (
        [pts["Fy"], pts["Fy2"], pts["By2"], pts["By"], pts["Fy"]],
        [pts["Fx2"], pts["Fx"], pts["F02"], pts["Bx2"], pts["Fx2"]],
        [pts["By3"], pts["Fy3"], pts["Bx2"], pts["By4"], pts["By3"]],
    ):
        pieces, split = _split_banquette_if_needed_U1F(ban)
        polys["banquettes"] += pieces
        split_any = split_any or split

    # D1 (gauche) — scinder selon la banquette gauche si nécessaire
    if d["D1"]:
        # Rectangle vertical sur la banquette gauche : de y=Fy.y à y=By_dL.y
        x0, x1 = 0, pts["F0"][0]
        y0 = pts["Fy"][1]
        y1 = pts["By_dL"][1]
        # Bornes complètes de l'assise gauche (sans méridienne) : Fy.y → By.y
        seat_y0, seat_y1 = pts["Fy"][1], pts["By"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
    if d["D2"]: polys["dossiers"].append([pts["D0x"], pts["D0"], pts["Dy"], pts["Fy"], pts["D0x"]])
    # --- Dossiers bas : 1 ou 2 rectangles selon scission de l'assise ---
    if d["D3"] or d["D4"] or d["D5"]:
        F0x, F0y = pts["F0"]
        xL_total = F0x
        xR_total = pts["F02"][0]
        # assise centrale = Fx → F02
        Lb = abs(pts["F02"][0] - pts["Fx"][0])
        if Lb > SPLIT_THRESHOLD:
            mid_x = _split_mid_int(pts["Fx"][0], pts["F02"][0])
            polys["dossiers"] += [
                _rectU(xL_total, 0, mid_x,  F0y),
                _rectU(mid_x,    0, xR_total, F0y),
            ]
        else:
            polys["dossiers"].append(_rectU(xL_total, 0, xR_total, F0y))
    # Ajout d'une bande de dossier bas-droite (D5) pour la variante v2.
    # Le polygone est défini lorsque le dossier bas est actif OU lorsque le dossier droit est actif.
    # Cela garantit la fermeture visuelle même si seul le dossier droit est présent.
    if d["D5"] or dossier_right:
        polys["dossiers"].append([pts["Dx2"], pts["D02"], pts["Dy3"], pts["Bx2"], pts["Dx2"]])
    if d["D6"]:
        # D6 (droit haut) — scinder selon la banquette droite si nécessaire
        x0, x1 = pts["D02x"][0], tx
        # Le dossier droit démarre à la hauteur Fy3.y (banquette droite en v2)
        y0 = pts["Fy3"][1]
        y1 = pts["By4_d"][1]
        seat_y0, seat_y1 = pts["Fy3"][1], pts["By4"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)

    if acc_left:
        if d["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])
    if acc_right:
        if d["D6"]:
            dy_top = pts.get("Dy4", pts.get("Dy3"))
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], dy_top, pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    # U1F v1/v2 — délimitation verticale Dx–Fx (jonction dossiers 3 et 4)
    if dossier_bas:
        F0y_local = pts["F0"][1]
        seam = max(0.2, min(0.8, F0y_local * 0.02))
        x_mid_candidates = []
        if "Dx" in pts:
            x_mid_candidates.append(pts["Dx"][0])
        if "Fx" in pts:
            x_mid_candidates.append(pts["Fx"][0])
        if x_mid_candidates:
            if len(x_mid_candidates) > 1:
                xm = 0.5 * (x_mid_candidates[0] + x_mid_candidates[1])
            else:
                xm = x_mid_candidates[0]
            polys["dossiers"].append(_rectU(xm - seam/2, 0, xm + seam/2, F0y_local))

    polys["split_flags"]={"any":split_any}
    return polys

def compute_points_U1F_v3(tx, ty_left, tz_right, profondeur=DEPTH_STD,
                          dossier_left=True, dossier_bas=True, dossier_right=True,
                          acc_left=True, acc_right=True,
                          meridienne_side=None, meridienne_len=0):
    if meridienne_side == 'g' and acc_left:
        raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
    if meridienne_side == 'd' and acc_right:
        raise ValueError("Méridienne droite interdite avec accoudoir droit.")

    A = profondeur + 20
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas  else 0

    pts = {}
    pts["D0"]=(0,0); pts["D0x"]=(F0x,0); pts["D0y"]=(0,F0y); pts["F0"]=(F0x, F0y)

    # Gauche
    pts["Fx"]  = (F0x + profondeur, F0y)
    pts["Fx2"] = (F0x + profondeur, F0y + profondeur)
    pts["Dx"]  = (F0x + profondeur, 0)

    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos  = (max(F0y + A, top_y_L_full - meridienne_len) if meridienne_side == 'g' else top_y_L_full)
    pts["By"]=(F0x, top_y_L_full); pts["By2"]=(F0x + profondeur, top_y_L_full)
    pts["Dy"]=(0, F0y + A); pts["Dy2"]=(0, top_y_L_dos); pts["By_dL"]=(F0x, top_y_L_dos)
    pts["Ay"]=(0, ty_left); pts["Ay2"]=(F0x + profondeur, ty_left); pts["Ay_"]=(F0x, ty_left)

    # Droite globale
    F02x = tx - (10 if dossier_right else 0)
    pts["F02"]=(F02x, F0y)
    pts["D02x"]=(F02x, 0)

    # Assise bas (côté angle)
    bx_x = F02x - (profondeur + 20)
    pts["Bx"]=(bx_x, F0y); pts["Bx2"]=(bx_x, F0y + profondeur); pts["Dx2"]=(bx_x, 0)

    # Colonne droite et hautesurs
    col_x = F02x - profondeur
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    top_y_R_dos  = (max(F0y + A, top_y_R_full - meridienne_len) if meridienne_side == 'd' else top_y_R_full)
    pts["Fy"]  = (col_x, F0y + A)
    pts["Fy2"] = (F02x,  F0y + A)
    # ajout alias Fy3 pour build_polys_U1F_v3 : Fy3 = Fy
    pts["Fy3"] = pts["Fy"]  # alias attendu par build_polys_U1F_v3
    pts["By3"] = (col_x, top_y_R_full)
    pts["By4"] = (F02x,  top_y_R_full)
    pts["By4_d"]=(F02x,  top_y_R_dos)
    pts["D02"]  = (tx, 0)
    pts["D02y"] = (tx, F0y)
    pts["Dy3"]  = (tx, top_y_R_dos)
    pts["Dy2R"] = (tx, F0y + A)  # pour D5/D6

    pts["Ax"]=(col_x, tz_right); pts["Ax2"]=(tx, tz_right); pts["Ax_par"]=(F02x, tz_right)

    if not dossier_bas:
        pts["D0y"]=(0, 0); pts["D02y"]=(tx, 0)

    # Bornes coussins (arrêt si méridienne)
    pts["By_cush"]  = (pts["By"][0],  min(pts["By"][1],  pts["Dy2"][1]))
    pts["By4_cush"] = (pts["By4"][0], min(pts["By4"][1], pts["By4_d"][1]))

    pts["_A"]=A; pts["_ty_canvas"]=max(ty_left, tz_right)
    pts["_draw"] = {"D1":bool(dossier_left), "D2":bool(dossier_bas), "D3":bool(dossier_bas),
                    "D4":bool(dossier_bas), "D5":bool(dossier_right), "D6":bool(dossier_right)}
    pts["_acc"]={"L":acc_left, "R":acc_right}
    return pts

def build_polys_U1F_v3(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True, dossier_right=True,
                       acc_left=True, acc_right=True):
    polys={"angle": [], "banquettes": [], "dossiers": [], "accoudoirs": []}
    d={"D1":dossier_left,"D2":dossier_bas,"D3":dossier_bas,"D4":dossier_bas,"D5":dossier_right,"D6":dossier_right}

    # Banquettes
    split_any=False
    ban_g = [pts["F0"], pts["By"], pts["By2"], pts["Fx"],  pts["F0"]]
    ban_b = [pts["Fx"], pts["Bx"], pts["Bx2"], pts["Fx2"], pts["Fx"]]
    ban_d = [pts["Fy"], pts["By3"], pts["By4"], pts["Fy2"], pts["Fy"]]
    for ban in (ban_g, ban_b, ban_d):
        pieces, split = _split_banquette_if_needed_U1F(ban)
        polys["banquettes"] += pieces
        split_any = split_any or split

    # Angle fromage gauche
    polys["angle"].append([pts["Bx"], pts["F02"], pts["Fy2"], pts["Fy"], pts["Bx2"], pts["Bx"]])

    # Dossiers
    if d["D1"]:
        # scinder D1 sur la banquette gauche si nécessaire
        x0, x1 = 0, pts["F0"][0]
        # Étirer le dossier gauche jusqu'à la base du canapé (y=0) pour éviter le « trou »
        y0 = 0
        y1 = pts["By_dL"][1]
        # Bornes complètes de l'assise gauche pour la scission (F0.y → By.y)
        seat_y0, seat_y1 = pts["F0"][1], pts["By"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
    # --- Dossiers bas : 1 ou 2 rectangles selon scission de l'assise ---
    if d["D2"] or d["D3"] or d["D4"]:
        F0x, F0y = pts["F0"]
        xL_total = F0x
        xR_total = pts["F02"][0]
        Lb = abs(pts["Bx"][0] - pts["Fx"][0])
        if Lb > SPLIT_THRESHOLD:
            mid_x = _split_mid_int(pts["Fx"][0], pts["Bx"][0])
            polys["dossiers"] += [
                _rectU(xL_total, 0, mid_x,  F0y),
                _rectU(mid_x,    0, xR_total, F0y),
            ]
        else:
            polys["dossiers"].append(_rectU(xL_total, 0, xR_total, F0y))
    if d["D5"]:
        polys["dossiers"].append([pts["D02x"], pts["Fy2"], pts["Dy2R"], pts["D02"], pts["D02x"]])
    if d["D6"]:
        # scinder D6 (droit haut) si nécessaire
        x0, x1 = pts["D02x"][0], tx
        y0 = pts["Fy3"][1]
        y1 = pts["By4_d"][1]
        seat_y0, seat_y1 = pts["Fy3"][1], pts["By4"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)

    # U1F v3 — délimitation verticale Dx–Fx (jonction dossiers 3 et 4)
    if dossier_bas:
        F0y_local = pts["F0"][1]
        seam = max(0.2, min(0.8, F0y_local * 0.02))
        x_mid_candidates = []
        if "Dx" in pts:
            x_mid_candidates.append(pts["Dx"][0])
        if "Fx" in pts:
            x_mid_candidates.append(pts["Fx"][0])
        if x_mid_candidates:
            if len(x_mid_candidates) > 1:
                xm = 0.5 * (x_mid_candidates[0] + x_mid_candidates[1])
            else:
                xm = x_mid_candidates[0]
            polys["dossiers"].append(_rectU(xm - seam/2, 0, xm + seam/2, F0y_local))

    # --- Overlay couture verticale Dx2–Bx pour délimiter le dossier bas (jonction D4/D5) ---
    # Dessinée en dernier dans les dossiers pour garantir la visibilité. Ceci reproduit le
    # comportement de la variante v4 pour rendre visible la séparation entre la banquette
    # centrale et la banquette droite (Dx2–Bx). Nous ne modifions aucune géométrie
    # existante : seule cette fine bande est ajoutée en overlay si le côté droit est actif.
    if d.get("D4") or d.get("D5"):
        F0y_local = pts["F0"][1]
        # épaisseur visuelle cohérente (~2 % de la hauteur du dossier bas), bornée entre 0.2 et 0.8 cm
        seam = max(0.2, min(0.8, F0y_local * 0.02))

        x_right_candidates = []
        if "Dx2" in pts:
            x_right_candidates.append(pts["Dx2"][0])
        if "Bx" in pts:
            x_right_candidates.append(pts["Bx"][0])

        if x_right_candidates:
            # On prend la moyenne des coordonnées pour robustesse en cas de léger décalage
            xr = sum(x_right_candidates) / len(x_right_candidates)
            polys["dossiers"].append(
                _rectU(xr - seam / 2, 0,
                       xr + seam / 2, F0y_local)
            )

    # Accoudoirs
    if acc_left:
        if d["D1"]:
            polys["accoudoirs"].append([pts["Ay"],  pts["Ay2"],  pts["By2"],  pts["Dy2"],  pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"],  pts["By2"],  pts["By"],   pts["Ay_"]])
    if acc_right:
        if d["D5"] or d["D6"]:
            dy_top = pts.get("Dy3", pts.get("Dy4"))
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], dy_top, pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    polys["split_flags"]={"any":split_any}
    return polys

def compute_points_U1F_v4(tx, ty_left, tz_right, profondeur=DEPTH_STD,
                          dossier_left=True, dossier_bas=True, dossier_right=True,
                          acc_left=True, acc_right=True,
                          meridienne_side=None, meridienne_len=0):
    if meridienne_side == 'g' and acc_left:
        raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
    if meridienne_side == 'd' and acc_right:
        raise ValueError("Méridienne droite interdite avec accoudoir droit.")

    A, F0x, F0y = _common_offsets_u1f(profondeur, dossier_left, dossier_bas, dossier_right)
    F02x = tx - (10 if dossier_right else 0)

    pts={}
    pts["D0"]=(0,0); pts["D0x"]=(F0x,0); pts["D0y"]=(0,F0y); pts["F0"]=(F0x,F0y)

    # GAUCHE
    pts["Dy"]=(0, F0y+profondeur)
    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos  = top_y_L_full if meridienne_side!='g' else max(F0y+profondeur, top_y_L_full - meridienne_len)

    pts["Fy"]=(F0x, F0y+profondeur); pts["Fy2"]=(F0x+profondeur, F0y+profondeur)
    pts["By"]=(F0x, top_y_L_full);   pts["By2"]=(F0x+profondeur, top_y_L_full)
    pts["Dy2"]=(0, top_y_L_dos)
    pts["By_dL"]=(F0x, top_y_L_dos)
    pts["Ay"]=(0, ty_left); pts["Ay2"]=(F0x+profondeur, ty_left); pts["Ay_"]=(F0x, ty_left)

    # BAS + angle droite
    pts["Fx"]=(F0x+profondeur, F0y); pts["Fx2"]=(F0x+profondeur, F0y+profondeur)
    bx_x = F02x - (profondeur+20)
    pts["Bx"]=(bx_x, F0y); pts["Bx2"]=(bx_x, F0y+profondeur); pts["Dx"]=(bx_x, 0)

    # DROITE
    col_x = F02x - profondeur
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    top_y_R_dos  = top_y_R_full if meridienne_side!='d' else max(F0y + (profondeur+20), top_y_R_full - meridienne_len)

    pts["Fy3"]=(col_x, F0y + (profondeur+20)); pts["Fy4"]=(F02x, F0y + (profondeur+20))
    pts["By3"]=(col_x, top_y_R_full); pts["By4"]=(F02x, top_y_R_full); pts["By4_d"]=(F02x, top_y_R_dos)
    pts["Ax"]=(col_x, tz_right); pts["Ax2"]=(tx, tz_right); pts["Ax_par"]=(F02x, tz_right)

    pts["D02x"]=(F02x, 0); pts["F02"]=(F02x, F0y)
    pts["D02"]=(tx, 0); pts["D02y"]=(tx, F0y)
    pts["Dy3"]=(tx, F0y + (profondeur+20)); pts["Dy4"]=(tx, top_y_R_dos)

    if not dossier_bas:
        pts["D0y"]=(0,0); pts["D02y"]=(tx,0)

    pts["By_cush"]  = (pts["By"][0],  min(pts["By"][1],  top_y_L_dos))
    pts["By4_cush"] = (pts["By4"][0], min(pts["By4"][1], top_y_R_dos))

    pts["_A"]=profondeur+20; pts["_ty_canvas"]=max(ty_left, tz_right)
    pts["_draw"]={
        "D1": bool(dossier_left), "D2": bool(dossier_left),
        "D3": bool(dossier_bas),  "D4": bool(dossier_bas),
        "D5": bool(dossier_right),"D6": bool(dossier_right),
    }
    pts["_acc"]={"L":acc_left, "R":acc_right}
    return pts

def build_polys_U1F_v4(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True, dossier_right=True,
                       acc_left=True, acc_right=True):
    polys={"angle": [], "banquettes": [], "dossiers": [], "accoudoirs": []}
    d=pts["_draw"]

    split_any=False
    for ban in (
        [pts["Fy"], pts["By"], pts["By2"], pts["Fy2"], pts["Fy"]],
        [pts["F0"], pts["Bx"], pts["Bx2"], pts["Fy"],  pts["F0"]],
        [pts["Fy4"], pts["By4"], pts["By3"], pts["Fy3"], pts["Fy4"]],
    ):
        pieces, split = _split_banquette_if_needed_U1F(ban)
        polys["banquettes"] += pieces
        split_any = split_any or split

    polys["angle"].append([pts["Bx"], pts["F02"], pts["Fy4"], pts["Fy3"], pts["Bx2"], pts["Bx"]])

    if d["D1"]:
        # D1 (gauche) — scinder selon la banquette gauche si nécessaire
        x0, x1 = 0, pts["F0"][0]
        y0 = pts["Fy"][1]            # hauteur de départ de la banquette gauche
        y1 = pts["By_dL"][1]         # hauteur maximale du dossier gauche (tenue compte méridienne)
        seat_y0, seat_y1 = pts["Fy"][1], pts["By"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
    if d["D2"]:
        polys["dossiers"].append([pts["D0x"], pts["D0"], pts["Dy"], pts["Fy"], pts["D0x"]])
    # --- Dossiers bas : 1 ou 2 rectangles selon scission de l'assise ---
    if d["D3"] or d["D4"]:
        F0x, F0y = pts["F0"]
        xL_total = F0x
        xR_total = pts["F02"][0]
        # largeur de la banquette centrale (F0 → Bx), comme dans la scission de l'assise
        Lb = abs(pts["Bx"][0] - pts["F0"][0])
        if Lb > SPLIT_THRESHOLD:
            # milieu identique à celui utilisé pour la scission de l'assise : médiane entre F0.x et Bx.x
            mid_x = _split_mid_int(pts["F0"][0], pts["Bx"][0])
            polys["dossiers"] += [
                _rectU(xL_total, 0, mid_x,  F0y),
                _rectU(mid_x,    0, xR_total, F0y),
            ]
        else:
            polys["dossiers"].append(_rectU(xL_total, 0, xR_total, F0y))
    if d["D5"]:
        polys["dossiers"].append([pts["D02x"], pts["Fy4"], pts["Dy3"], pts["D02"], pts["D02x"]])
    if d["D6"]:
        # D6 (droit haut) — scinder selon la banquette droite si nécessaire
        x0, x1 = pts["D02x"][0], tx
        # Le dossier droit démarre à Fy4.y (banquette droite pour v4)
        y0 = pts["Fy4"][1]
        y1 = pts["By4_d"][1]
        seat_y0, seat_y1 = pts["Fy4"][1], pts["By4"][1]
        polys["dossiers"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)

    # U1F v4 — délimitation verticale Dx2–Bx (jonction dossiers 4 et 5)
    if dossier_bas:
        F0y_local = pts["F0"][1]
        seam = max(0.2, min(0.8, F0y_local * 0.02))
        x_right_candidates = []
        if "Dx2" in pts:
            x_right_candidates.append(pts["Dx2"][0])
        if "Bx" in pts:
            x_right_candidates.append(pts["Bx"][0])
        if x_right_candidates:
            if len(x_right_candidates) > 1:
                xr = 0.5 * (x_right_candidates[0] + x_right_candidates[1])
            else:
                xr = x_right_candidates[0]
            polys["dossiers"].append(_rectU(xr - seam/2, 0, xr + seam/2, F0y_local))

    if acc_left:
        if d["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])

    if acc_right:
        has_right = (d["D5"] or d["D6"])
        if has_right:
            dy_top = pts.get("Dy4", pts.get("Dy3"))
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], dy_top, pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    polys["split_flags"]={"any":split_any}
    return polys

# --- rendu commun + wrappers (U1F) ---
def _render_common_U1F(variant, tx, ty_left, tz_right, profondeur,
                       dossier_left, dossier_bas, dossier_right,
                       acc_left, acc_right,
                       meridienne_side, meridienne_len,
                       coussins, traversins, couleurs, window_title):
    comp = {"v1":compute_points_U1F_v1, "v2":compute_points_U1F_v2,
            "v3":compute_points_U1F_v3, "v4":compute_points_U1F_v4}[variant]
    build= {"v1":build_polys_U1F_v1,   "v2":build_polys_U1F_v2,
            "v3":build_polys_U1F_v3,   "v4":build_polys_U1F_v4}[variant]

    trv = _parse_traversins_spec(traversins, allowed={"g","d"})
    legend_items = _resolve_and_apply_colors(couleurs)

    pts = comp(tx, ty_left, tz_right, profondeur,
               dossier_left, dossier_bas, dossier_right,
               acc_left, acc_right,
               meridienne_side, meridienne_len)
    polys = build(pts, tx, ty_left, tz_right, profondeur,
                  dossier_left, dossier_bas, dossier_right,
                  acc_left, acc_right)
    _assert_banquettes_max_250(polys)

    ty_canvas = max(ty_left, tz_right)
    screen = turtle.Screen(); screen.setup(WIN_W, WIN_H)
    screen.title(f"U1F {variant} — {window_title} — tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur}")
    t = turtle.Turtle(visible=False); t.speed(0); screen.tracer(False)
    tr = WorldToScreen(tx, ty_canvas, WIN_W, WIN_H, PAD_PX, ZOOM)

    # (Quadrillage et repères supprimés)

    for p in polys["dossiers"]:
        xs=[pp[0] for pp in p]; ys=[pp[1] for pp in p]
        if (max(xs)-min(xs) > 1e-9) and (max(ys)-min(ys) > 1e-9):
            draw_polygon_cm(t, tr, p, fill=COLOR_DOSSIER)
    for p in polys["banquettes"]: draw_polygon_cm(t, tr, p, fill=COLOR_ASSISE)
    for p in polys["accoudoirs"]: draw_polygon_cm(t, tr, p, fill=COLOR_ACC)
    for p in polys["angle"]:      draw_polygon_cm(t, tr, p, fill=COLOR_ASSISE)

    # Traversins + comptage
    n_traversins = _draw_traversins_U_side_F02(t, tr, pts, profondeur, trv)

    draw_double_arrow_vertical_cm(t, tr, -25,   0, ty_left,   f"{ty_left} cm")
    draw_double_arrow_vertical_cm(t, tr,  tx+25,0, tz_right,   f"{tz_right} cm")
    draw_double_arrow_horizontal_cm(t, tr, -25, 0, tx,   f"{tx} cm")

    A = pts["_A"]
    if polys["angle"]:
        # Dimensions d’angle sur deux lignes : première ligne sans unité suivie d'un « x », deuxième ligne avec « cm »
        label_poly(t, tr, polys["angle"][0], f"{A}x\n{A} cm")
    banquette_sizes = []
    for poly in polys["banquettes"]:
        L, P = banquette_dims(poly)
        banquette_sizes.append((L, P))
        # Afficher la longueur sans unité suivie d'un « x », et la profondeur avec « cm »
        text = f"{L}x\n{P} cm"
        xs = [pp[0] for pp in poly]
        ys = [pp[1] for pp in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Décaler horizontalement si la banquette est plus haute que large
        if bb_h >= bb_w:
            # Centre X de la banquette
            cx = sum(xs) / len(xs)
            # Réduire les offsets : 3 cm en moins sur les branches verticales
            # Branche gauche : CUSHION_DEPTH+7 (22 cm). Branche droite : -(CUSHION_DEPTH-8) (-7 cm).
            dx = (CUSHION_DEPTH + 7) if cx < tx / 2.0 else -(CUSHION_DEPTH - 8)
            label_poly_offset_cm(t, tr, poly, text, dx_cm=dx, dy_cm=0.0)
        else:
            label_poly(t, tr, poly, text)
    # Annoter dossiers et accoudoirs avec leurs épaisseurs
    _label_backrests_armrests(t, tr, polys)

    # ===== COUSSINS =====
    spec = _parse_coussins_spec(coussins)
    # Préparer des compteurs pour le rapport console afin de ventiler le
    # nombre de coussins selon les tailles 65 cm, 80 cm, 90 cm et valise.
    nb_coussins_65 = 0
    nb_coussins_80 = 0
    nb_coussins_90 = 0
    nb_coussins_valise = 0
    if spec["mode"] == "auto":
        size = _choose_cushion_size_auto_U1F(pts, traversins=trv)
        nb_coussins = _draw_coussins_U1F(t, tr, pts, size, traversins=trv)
        total_line = f"{coussins} → {nb_coussins} × {size} cm"
        # Répartition des coussins selon la taille choisie en mode auto
        if size == 65:
            nb_coussins_65 = nb_coussins
        elif size == 80:
            nb_coussins_80 = nb_coussins
        elif size == 90:
            nb_coussins_90 = nb_coussins
        else:
            nb_coussins_valise = nb_coussins
    elif spec["mode"] == "80-90":
        best = _optimize_80_90_U1F(pts, traversins=trv)
        if not best:
            raise ValueError('Aucune configuration "80-90" valide pour U1F.')
        sizes = best["sizes"]
        shiftL, shiftR = best["shifts"]
        nb_coussins = _draw_U1F_with_sizes(
            t, tr, pts, sizes, shiftL, shiftR, traversins=trv
        )
        sb, sg, sd = sizes["bas"], sizes["gauche"], sizes["droite"]
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg, "droite": sd},
            best.get("counts", best.get("eval", {}).get("counts")),
            nb_coussins,
        )
        # Répartition des coussins selon les tailles pour chaque côté en mode 80‑90
        counts_dict = best.get("counts", best.get("eval", {}).get("counts"))
        if counts_dict:
            for side, size_val in [("bas", sb), ("gauche", sg), ("droite", sd)]:
                c = counts_dict.get(side, 0)
                if not c:
                    continue
                if size_val == 65:
                    nb_coussins_65 += c
                elif size_val == 80:
                    nb_coussins_80 += c
                elif size_val == 90:
                    nb_coussins_90 += c
                else:
                    nb_coussins_valise += c
    elif spec["mode"] == "fixed":
        size = int(spec["fixed"])
        nb_coussins = _draw_coussins_U1F(t, tr, pts, size, traversins=trv)
        total_line = f"{coussins} → {nb_coussins} × {size} cm"
        # Répartition des coussins selon la taille fixe
        if size == 65:
            nb_coussins_65 = nb_coussins
        elif size == 80:
            nb_coussins_80 = nb_coussins
        elif size == 90:
            nb_coussins_90 = nb_coussins
        else:
            nb_coussins_valise = nb_coussins
    else:
        best = _optimize_valise_U1F(pts, spec["range"], spec["same"], traversins=trv)
        if not best:
            raise ValueError("Aucune configuration valise valide pour U1F.")
        sizes = best["sizes"]
        shiftL, shiftR = best["shifts"]
        nb_coussins = _draw_U1F_with_sizes(t, tr, pts, sizes, shiftL, shiftR, traversins=trv)
        sb, sg, sd = sizes["bas"], sizes["gauche"], sizes["droite"]
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg, "droite": sd},
            best.get("counts", best.get("eval", {}).get("counts")),
            nb_coussins,
        )
        # En mode valise, tous les coussins sont considérés comme des coussins valises
        nb_coussins_valise = nb_coussins

    # Titre + légende (U → haut-centre)
    draw_title_center(t, tr, tx, ty_canvas, "Canapé en U avec un angle")
    draw_legend(t, tr, tx, ty_canvas, items=legend_items, pos="top-center")

    screen.tracer(True); t.hideturtle()

    # Calculs pour le rapport détaillé
    dossier_bonus = int(polys.get("split_flags",{}).get("any", False))
    dossiers_count = _compute_dossiers_count(polys)
    # Formater le nombre de dossiers en évitant les décimales inutiles
    dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    nb_banquettes = len(polys["banquettes"])
    nb_banquettes_angle = len(polys["angle"])
    nb_accoudoirs = len(polys["accoudoirs"])
    # Dimensions des dossiers
    dossier_dims = []
    for dp in polys["dossiers"]:
        try:
            L_d, P_d = banquette_dims(dp)
        except Exception:
            # Si le calcul échoue, sauter le dossier
            continue
        dossier_dims.append((L_d, P_d))

    # Rapport classique
    print(f"=== Rapport U1F {variant} ===")
    print(f"Dimensions : tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — profondeur={profondeur} (A={A})")
    print(f"Banquettes : {nb_banquettes} → {banquette_sizes}")
    print(f"Dossiers : {dossiers_str} (+{dossier_bonus} via scission) | Accoudoirs : {nb_accoudoirs}")
    print(f"Banquettes d’angle : {nb_banquettes_angle}")
    print(f"Angles : {nb_banquettes_angle} × {A}×{A} cm")
    # Mise à jour du format des traversins (nouvelle largeur 20 cm)
    print(f"Traversins : {n_traversins} × 70x20")
    print(f"Coussins : {total_line}")

    # Rapport détaillé
    print()
    print("À partir des données console :")
    print(f"Dimensions : tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — profondeur={profondeur} (A={A})")
    print(f"Nombre de banquettes : {nb_banquettes}")
    print(f"Nombre de banquette d’angle : {nb_banquettes_angle}")
    print(f"Nombre de dossiers : {dossiers_str}")
    print(f"Nombre d’accoudoir : {nb_accoudoirs}")
    # Afficher également les dimensions des accoudoirs
    _print_accoudoirs_dimensions(polys)
    # Affichage détaillé des dossiers : pour la variante v1, utiliser
    # l’implémentation spécifique U1F v1.  Pour les autres variantes,
    # conserver l’heuristique générique basée sur les polygones.
    # Calculer les étiquettes et tailles des banquettes pour les dossiers.
    _banquette_labels = _compute_banquette_labels(polys)
    # Les dimensions des banquettes droites sont déjà collectées dans
    # ``banquette_sizes`` lors de l’annotation graphique.  Pour l’angle,
    # extraire la longueur du côté le plus long (premier retour de
    # banquette_dims) pour servir de dimension d’angle.
    _angle_sizes = []
    for _poly_angle in polys.get("angle", []):
        try:
            _L_angle, _P_angle = banquette_dims(_poly_angle)
            _angle_sizes.append(_L_angle)
        except Exception:
            continue
    if variant == "v1":
        # Variante U1F v1 : utiliser la fonction dédiée
        _print_dossiers_dimensions_U1F_v1(
            _banquette_labels,
            banquette_sizes,
            _angle_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    elif variant == "v2":
        # Variante U1F v2 : utiliser la fonction dédiée
        _print_dossiers_dimensions_U1F_v2(
            _banquette_labels,
            banquette_sizes,
            _angle_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    elif variant == "v3":
        # Variante U1F v3 : utiliser la fonction dédiée
        _print_dossiers_dimensions_U1F_v3(
            _banquette_labels,
            banquette_sizes,
            _angle_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    elif variant == "v4":
        # Variante U1F v4 : utiliser la fonction dédiée
        _print_dossiers_dimensions_U1F_v4(
            _banquette_labels,
            banquette_sizes,
            _angle_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    else:
        # Autres variantes : fallback sur l’heuristique générique
        _print_dossiers_dimensions(polys)
    # Dimensions des mousses (banquettes droites)
    # Utiliser des étiquettes "n" et "n-bis" pour regrouper les scissions par branche
    _banquette_labels = _compute_banquette_labels(polys)
    for label, (L_b, P_b) in zip(_banquette_labels, banquette_sizes):
        print(f"Dimension mousse {label} : {L_b}, {P_b}")
    # Dimensions des mousses d’angle
    for i, ang_poly in enumerate(polys["angle"], start=1):
        try:
            L_a, P_a = banquette_dims(ang_poly)
            print(f"Dimension mousse angle {i} : {L_a}, {P_a}")
        except Exception:
            continue
    # Les dimensions des dossiers ne sont plus affichées individuellement pour U1F
    # Elles peuvent être calculées via `banquette_dims` mais ne sont pas listées ici.
    # Répartition des coussins
    print(f"Nombre de coussins 65cm : {nb_coussins_65}")
    print(f"Nombre de coussins 80cm : {nb_coussins_80}")
    print(f"Nombre de coussins 90cm : {nb_coussins_90}")
    print(f"Nombre de coussins valises total : {nb_coussins_valise}")
    print(f"Nombre de traversin : {n_traversins}")
    turtle.done()

def _dry_polys_for_U1F_variant(tx, ty_left, tz_right, profondeur,
                               dossier_left, dossier_bas, dossier_right,
                               acc_left, acc_right,
                               meridienne_side, meridienne_len,
                               variant):
    """
    Calcule (pts, polys) pour une variante U1F donnée sans rendre le dessin.
    Utile pour comparer plusieurs variantes et choisir celle qui convient.
    """
    comp = {
        "v1": compute_points_U1F_v1,
        "v2": compute_points_U1F_v2,
        "v3": compute_points_U1F_v3,
        "v4": compute_points_U1F_v4,
    }[variant]
    build = {
        "v1": build_polys_U1F_v1,
        "v2": build_polys_U1F_v2,
        "v3": build_polys_U1F_v3,
        "v4": build_polys_U1F_v4,
    }[variant]
    pts = comp(
        tx, ty_left, tz_right, profondeur,
        dossier_left, dossier_bas, dossier_right,
        acc_left, acc_right,
        meridienne_side, meridienne_len,
    )
    polys = build(
        pts, tx, ty_left, tz_right, profondeur,
        dossier_left, dossier_bas, dossier_right,
        acc_left, acc_right,
    )
    return pts, polys

def render_U1F(tx, ty_left, tz_right, profondeur=DEPTH_STD,
               dossier_left=True, dossier_bas=True, dossier_right=True,
               acc_left=True, acc_right=True,
               meridienne_side=None, meridienne_len=0,
               coussins="auto",
               variant="auto",
               traversins=None,
               couleurs=None,
               window_title="U1F — auto"):
    """
    Rendu générique pour les U1F. Permet de forcer une variante (v1/v2/v3/v4)
    ou de laisser le choix automatique (auto) entre les variantes les plus simples (v1 et v3).
    """
    v_norm = (variant or "auto").lower()
    # Forcer explicitement une variante
    if v_norm in {"v1", "v2", "v3", "v4"}:
        if v_norm == "v1":
            return render_U1F_v1(
                tx=tx, ty_left=ty_left, tz_right=tz_right, profondeur=profondeur,
                dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                acc_left=acc_left, acc_right=acc_right,
                meridienne_side=meridienne_side, meridienne_len=meridienne_len,
                coussins=coussins, traversins=traversins, couleurs=couleurs,
                window_title=window_title,
            )
        if v_norm == "v2":
            return render_U1F_v2(
                tx=tx, ty_left=ty_left, tz_right=tz_right, profondeur=profondeur,
                dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                acc_left=acc_left, acc_right=acc_right,
                meridienne_side=meridienne_side, meridienne_len=meridienne_len,
                coussins=coussins, traversins=traversins, couleurs=couleurs,
                window_title=window_title,
            )
        if v_norm == "v3":
            return render_U1F_v3(
                tx=tx, ty_left=ty_left, tz_right=tz_right, profondeur=profondeur,
                dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                acc_left=acc_left, acc_right=acc_right,
                meridienne_side=meridienne_side, meridienne_len=meridienne_len,
                coussins=coussins, traversins=traversins, couleurs=couleurs,
                window_title=window_title,
            )
        if v_norm == "v4":
            return render_U1F_v4(
                tx=tx, ty_left=ty_left, tz_right=tz_right, profondeur=profondeur,
                dossier_left=dossier_left, dossier_bas=dossier_bas, dossier_right=dossier_right,
                acc_left=acc_left, acc_right=acc_right,
                meridienne_side=meridienne_side, meridienne_len=meridienne_len,
                coussins=coussins, traversins=traversins, couleurs=couleurs,
                window_title=window_title,
            )
    # Mode automatique: choisir la variante la plus simple entre v1 et v3
    candidates = ("v1", "v3")
    best_variant = None
    best_nb_ban = float("inf")
    best_scissions = float("inf")
    def _count_scissions(polys):
        base = 3
        nb = len(polys.get("banquettes", []))
        return max(0, nb - base)
    for var in candidates:
        try:
            _pts, _polys = _dry_polys_for_U1F_variant(
                tx, ty_left, tz_right, profondeur,
                dossier_left, dossier_bas, dossier_right,
                acc_left, acc_right,
                meridienne_side, meridienne_len,
                var,
            )
        except ValueError:
            continue
        nb_ban = len(_polys.get("banquettes", []))
        sci = _count_scissions(_polys)
        if (nb_ban < best_nb_ban) or (nb_ban == best_nb_ban and sci < best_scissions):
            best_variant = var
            best_nb_ban = nb_ban
            best_scissions = sci
    if best_variant is None:
        best_variant = "v1"
    return _render_common_U1F(
        best_variant,
        tx, ty_left, tz_right, profondeur,
        dossier_left, dossier_bas, dossier_right,
        acc_left, acc_right,
        meridienne_side, meridienne_len,
        coussins, traversins, couleurs,
        window_title,
    )

def render_U1F_v1(*args, **kwargs):
    if "traversins" not in kwargs: kwargs["traversins"]=None
    if "couleurs" not in kwargs: kwargs["couleurs"]=None
    # compat. anciens appels : ty/tz -> ty_left/tz_right
    if "ty_left" not in kwargs and "ty" in kwargs: kwargs["ty_left"] = kwargs.pop("ty")
    if "tz_right" not in kwargs and "tz" in kwargs: kwargs["tz_right"] = kwargs.pop("tz")
    _render_common_U1F("v1", *args, **kwargs)
def render_U1F_v2(*args, **kwargs):
    if "traversins" not in kwargs: kwargs["traversins"]=None
    if "couleurs" not in kwargs: kwargs["couleurs"]=None
    if "ty_left" not in kwargs and "ty" in kwargs: kwargs["ty_left"] = kwargs.pop("ty")
    if "tz_right" not in kwargs and "tz" in kwargs: kwargs["tz_right"] = kwargs.pop("tz")
    _render_common_U1F("v2", *args, **kwargs)
def render_U1F_v3(*args, **kwargs):
    if "traversins" not in kwargs: kwargs["traversins"]=None
    if "couleurs" not in kwargs: kwargs["couleurs"]=None
    if "ty_left" not in kwargs and "ty" in kwargs: kwargs["ty_left"] = kwargs.pop("ty")
    if "tz_right" not in kwargs and "tz" in kwargs: kwargs["tz_right"] = kwargs.pop("tz")
    _render_common_U1F("v3", *args, **kwargs)
def render_U1F_v4(*args, **kwargs):
    if "traversins" not in kwargs: kwargs["traversins"]=None
    if "couleurs" not in kwargs: kwargs["couleurs"]=None
    if "ty_left" not in kwargs and "ty" in kwargs: kwargs["ty_left"] = kwargs.pop("ty")
    if "tz_right" not in kwargs and "tz" in kwargs: kwargs["tz_right"] = kwargs.pop("tz")
    _render_common_U1F("v4", *args, **kwargs)

# =====================================================================
# ======================  L (no fromage) v1 + v2  =====================
# =====================================================================
def compute_points_LNF_v2(tx, ty, profondeur=DEPTH_STD,
                          dossier_left=True, dossier_bas=True,
                          acc_left=True, acc_bas=True,
                          meridienne_side=None, meridienne_len=0):
    prof = profondeur; pts = {}
    if dossier_left and dossier_bas:         F0x, F0y = 10, 10; D0x0=(10,0); D0y0=(0,10)
    elif (not dossier_left) and dossier_bas: F0x, F0y = 0, 10;  D0x0=(0,0);  D0y0=(0,10)
    elif dossier_left and (not dossier_bas): F0x, F0y = 10, 0;  D0x0=(10,0); D0y0=(0,0)
    else:                                    F0x, F0y = 0, 0;   D0x0=(0,0);  D0y0=(0,0)

    pts["D0"]=(0,0); pts["D0x"]=D0x0; pts["D0y"]=D0y0; pts["F0"]=(F0x,F0y)

    top_y = ty - (ACCOUDOIR_THICK if acc_left else 0)
    pts["Dy"]  =(0, F0y+prof); pts["Dy2"]=(0, top_y); pts["Ay"]=(0, ty)
    pts["Fy"]  =(F0x, F0y+prof); pts["By"]=(F0x, top_y)
    pts["Ay2"] =(F0x+prof, ty); pts["By2"]=(F0x+prof, top_y); pts["Ay_par"]=(F0x, ty)

    stop_x = tx - (ACCOUDOIR_THICK if acc_bas else 0)
    pts["Dx"]=(stop_x,0); pts["Bx"]=(stop_x,F0y); pts["Bx2"]=(stop_x,F0y+prof)
    pts["Ax"]=(tx,0); pts["Ax2"]=(tx,F0y+prof); pts["Ax_par"]=(tx,F0y)

    if meridienne_side=='g' and meridienne_len>0:
        mer_y=max(pts["Fy"][1], top_y - meridienne_len); mer_y=min(mer_y, top_y)
        pts["By_mer"]=(pts["By"][0],mer_y); pts["By2_mer"]=(pts["By2"][0],mer_y); pts["Dy2"]=(0,mer_y)
    if meridienne_side=='b' and meridienne_len>0:
        mer_x=min(stop_x, tx - meridienne_len)
        pts["Bx_mer"]=(mer_x, pts["Bx"][1]); pts["Bx2_mer"]=(mer_x, pts["Bx2"][1]); pts["Dx_mer"]=(mer_x,0)

    pts["_tx"], pts["_ty"] = tx, ty
    return pts

def build_polys_LNF_v2(pts, tx, ty, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True,
                       acc_left=True, acc_bas=True,
                       meridienne_side=None, meridienne_len=0):
    polys={"banquettes":[],"dossiers":[],"accoudoirs":[]}

    Fy=(pts["Fy"][0], pts["Fy"][1]); Fy2=(pts["Fy"][0]+profondeur, pts["Fy"][1])
    By=pts.get("By"); By2=pts.get("By2")
    ban_g=[Fy, By, By2, Fy2, Fy]
    split_left=False; mid_y_left=None
    Lg = abs(By2[1] - Fy2[1])
    if Lg > SPLIT_THRESHOLD:
        split_left=True; mid_y_left=_split_mid_int(Fy2[1], By2[1])
        low  = [(Fy[0],Fy[1]),(Fy2[0],Fy2[1]),(Fy2[0],mid_y_left),(Fy[0],mid_y_left),(Fy[0],Fy[1])]
        high = [(Fy[0],mid_y_left),(Fy2[0],mid_y_left),(By2[0],By2[1]),(By[0],By[1]),(Fy[0],mid_y_left)]
        polys["banquettes"] += [low, high]
    else:
        polys["banquettes"].append(ban_g)

    F0=pts["F0"]; Bx=pts["Bx"]; Bx2=pts["Bx2"]
    ban_b=[F0, Bx, Bx2, pts["Fy"], F0]
    split_bas=False; mid_x_bas=None
    Lb = abs(Bx2[0] - pts["Fy"][0])
    if Lb > SPLIT_THRESHOLD:
        split_bas=True; mid_x_bas=_split_mid_int(pts["Fy"][0], Bx2[0])
        left  = [(F0[0],F0[1]),(mid_x_bas,F0[1]),(mid_x_bas,pts["Fy"][1]),(pts["Fy"][0],pts["Fy"][1]),(F0[0],F0[1])]
        right = [(mid_x_bas,F0[1]),(Bx[0],Bx[1]),(Bx2[0],Bx2[1]),(mid_x_bas,pts["Fy"][1]),(mid_x_bas,F0[1])]
        polys["banquettes"] += [left, right]
    else:
        polys["banquettes"].append(ban_b)

    if dossier_left:
        if split_left:
            F0x=pts["F0"][0]; y0=pts["Dy"][1]; yTop=pts.get("By_mer", pts["By"])[1]
            d1b=[(0,y0),(F0x,y0),(F0x,mid_y_left),(0,mid_y_left),(0,y0)]
            d1h=[(0,mid_y_left),(F0x,mid_y_left),(F0x,yTop),(0,yTop),(0,mid_y_left)]
            polys["dossiers"] += [d1b, d1h]
        else:
            By_use = pts.get("By_mer", pts["By"])
            polys["dossiers"].append([pts["Dy2"], By_use, pts["Fy"], pts["Dy"], pts["Dy2"]])
    if dossier_left:
        polys["dossiers"].append([pts["D0x"], pts["D0"], pts["Dy"], pts["Fy"], pts["D0x"]])
    if dossier_bas:
        Bx_use = pts.get("Bx_mer", pts["Bx"]); Dx_use = pts.get("Dx_mer", pts["Dx"])
        if split_bas:
            yTop=pts["F0"][1]
            d3g=[(mid_x_bas,0),(pts["D0x"][0],0),(pts["D0x"][0],yTop),(mid_x_bas,yTop),(mid_x_bas,0)]
            d3d=[(Dx_use[0],0),(mid_x_bas,0),(mid_x_bas,yTop),(Bx_use[0],yTop),(Dx_use[0],0)]
            polys["dossiers"] += [d3g, d3d]
        else:
            polys["dossiers"].append([Dx_use, pts["D0x"], pts["F0"], Bx_use, Dx_use])

    if acc_left:
        if dossier_left:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["By"], pts["Ay_par"], pts["Ay2"], pts["By2"], pts["By"]])
    if acc_bas:
        if dossier_bas:
            polys["accoudoirs"].append([pts["Dx"], pts["Ax"], pts["Ax2"], pts["Bx2"], pts["Dx"]])
        else:
            polys["accoudoirs"].append([pts["Bx"], pts["Ax_par"], pts["Ax2"], pts["Bx2"], pts["Bx"]])

    polys["split_flags"]={"left":split_left,"bottom":split_bas}
    return polys

def compute_points_LNF_v1(tx, ty, profondeur=DEPTH_STD,
                          dossier_left=True, dossier_bas=True,
                          acc_left=True, acc_bas=True,
                          meridienne_side=None, meridienne_len=0):
    prof=profondeur; pts={}
    if dossier_left and dossier_bas:         F0x,F0y=10,10; D0x0=(10,0); D0y0=(0,10)
    elif (not dossier_left) and dossier_bas: F0x,F0y=0,10;  D0x0=(0,0);  D0y0=(0,10)
    elif dossier_left and (not dossier_bas): F0x,F0y=10,0;  D0x0=(10,0); D0y0=(0,0)
    else:                                    F0x,F0y=0,0;   D0x0=(0,0);  D0y0=(0,0)

    pts["D0"]=(0,0); pts["D0x"]=D0x0; pts["D0y"]=D0y0; pts["F0"]=(F0x,F0y)
    top_y = ty - (ACCOUDOIR_THICK if acc_left else 0)
    pts["Dy2"]=(0, top_y); pts["Ay"] =(0, ty); pts["By"] =(F0x, top_y)
    pts["Ay2"]=(F0x+prof, ty); pts["By2"]=(F0x+prof, top_y)

    stop_x = tx - (ACCOUDOIR_THICK if acc_bas else 0)
    pts["Dy"] =(0, F0y+prof)
    pts["Fx"] =(F0x+prof, F0y); pts["Fx2"]=(F0x+prof, F0y+prof)
    pts["Bx"] =(stop_x, F0y);   pts["Bx2"]=(stop_x, F0y+prof)
    pts["Dx"] =(F0x+prof, 0);   pts["DxR"]=(stop_x, 0)
    pts["Ax"] =(tx, 0); pts["Ax2"]=(tx, F0y+prof)
    pts["Ay_par"]=(F0x, ty); pts["Ax_par"]=(tx, F0y)

    if meridienne_side=='g' and meridienne_len>0:
        mer_y=max(F0y, top_y - meridienne_len); mer_y=min(mer_y, top_y)
        pts["By_mer"]=(pts["By"][0],mer_y); pts["By2_mer"]=(pts["By2"][0],mer_y); pts["Dy2"]=(0,mer_y)
    if meridienne_side=='b' and meridienne_len>0:
        mer_x=min(stop_x, tx - meridienne_len)
        pts["Bx_mer"]=(mer_x, pts["Bx"][1]); pts["Bx2_mer"]=(mer_x, pts["Bx2"][1]); pts["DxR_mer"]=(mer_x,0)
    pts["_tx"], pts["_ty"]=tx,ty
    return pts

def build_polys_LNF_v1(pts, tx, ty, profondeur=DEPTH_STD,
                       dossier_left=True, dossier_bas=True,
                       acc_left=True, acc_bas=True,
                       meridienne_side=None, meridienne_len=0):
    polys={"banquettes":[], "dossiers":[], "accoudoirs":[]}

    F0=pts["F0"]; Fx=pts["Fx"]; By=pts.get("By"); By2=pts.get("By2")
    ban_g=[F0, By, By2, Fx, F0]
    split_left=False; mid_y_left=None
    # IMPORTANT : ne pas tronquer la banquette par la méridienne.
    # La méridienne se matérialise par l'absence de dossier au-dessus,
    # l'assise doit rester à la hauteur "By/By2" (pleine hauteur).
    top_y = By2[1]; base_y = F0[1]
    Lg = abs(top_y - base_y)
    if Lg > SPLIT_THRESHOLD:
        split_left=True; mid_y_left=_split_mid_int(base_y, top_y)
        lower=[(F0[0],base_y),(Fx[0],base_y),(Fx[0],mid_y_left),(F0[0],mid_y_left),(F0[0],base_y)]
        upper=[(F0[0],mid_y_left),(Fx[0],mid_y_left),(By2[0],top_y),(By[0],top_y),(F0[0],mid_y_left)]
        polys["banquettes"] += [lower, upper]
    else:
        polys["banquettes"].append(ban_g)

    Bx=pts["Bx"]; Bx2=pts["Bx2"]; Fx2=pts["Fx2"]
    ban_b=[pts["Fx"], Bx, Bx2, Fx2, pts["Fx"]]
    split_bas=False; mid_x_bas=None
    Lb = abs(Bx2[0] - pts["Fx"][0])
    if Lb > SPLIT_THRESHOLD:
        split_bas=True; mid_x_bas=_split_mid_int(pts["Fx"][0], Bx2[0])
        left =[ (pts["Fx"][0], pts["Fx"][1]), (mid_x_bas, pts["Fx"][1]),
                (mid_x_bas, Fx2[1]), (Fx2[0], Fx2[1]), (pts["Fx"][0], pts["Fx"][1]) ]
        right=[ (mid_x_bas, pts["Fx"][1]), (Bx[0],Bx[1]), (Bx2[0],Bx2[1]),
                (mid_x_bas, Fx2[1]), (mid_x_bas, pts["Fx"][1]) ]
        polys["banquettes"] += [left, right]
    else:
        polys["banquettes"].append(ban_b)

    if dossier_left:
        By_use = pts.get("By_mer", pts["By"])
        if split_left:
            x0=0; x1=pts["D0x"][0]; y_base=0; y_top=By_use[1]; y_mid=mid_y_left
            d1_bas=[(x0,y_base),(x1,y_base),(x1,y_mid),(x0,y_mid),(x0,y_base)]
            d1_haut=[(x0,y_mid),(x1,y_mid),(x1,y_top),(x0,y_top),(x0,y_mid)]
            polys["dossiers"] += [d1_bas, d1_haut]
        else:
            polys["dossiers"].append([pts["D0"], pts["Dy2"], By_use, pts["D0x"], pts["D0"]])
    if dossier_left:
        polys["dossiers"].append([pts["D0x"], pts["Dx"], pts["Fx"], pts["F0"], pts["D0x"]])
    if dossier_bas:
        DxR_use = pts.get("DxR_mer", pts["DxR"]); Bx_use = pts.get("Bx_mer", pts["Bx"])
        if split_bas:
            yTop = pts["F0"][1]
            d3_g = [(mid_x_bas,0),(pts["Dx"][0],0),(pts["Dx"][0],yTop),(mid_x_bas,yTop),(mid_x_bas,0)]
            d3_d = [(DxR_use[0],0),(mid_x_bas,0),(mid_x_bas,yTop),(Bx_use[0],yTop),(DxR_use[0],0)]
            polys["dossiers"] += [d3_g, d3_d]
        else:
            polys["dossiers"].append([pts["Dx"], DxR_use, Bx_use, pts["Fx"], pts["Dx"]])
        # --- retour gauche si aucun dossier gauche (False ou None) et pas de méridienne bas
        if (dossier_left is None or dossier_left is False) and (meridienne_side not in ('b','B','bas','bottom')):
            # Ajoute un demi-dossier pour fermer la zone entre D0x/F0 et Dx/Fx
            polys["dossiers"].append([pts["D0x"], pts["Dx"], pts["Fx"], pts["F0"], pts["D0x"]])

    if acc_left:
        if dossier_left:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_par"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_par"]])
    if acc_bas:
        if dossier_bas:
            polys["accoudoirs"].append([pts["DxR"], pts["Ax"], pts["Ax2"], pts["Bx2"], pts["DxR"]])
        else:
            polys["accoudoirs"].append([pts["Bx"], pts["Ax_par"], pts["Ax2"], pts["Bx2"], pts["Bx"]])

    polys["split_flags"]={"left":split_left,"bottom":split_bas}
    return polys

def _choose_cushion_size_auto_L(pts, traversins=None):
    """
    Choix automatique de la taille de coussins (65/80/90) pour un L.
    Critère : choisir le standard qui permet de couvrir la plus grande
    surface de canapé (≈ nb_coussins * taille), en tenant compte des
    traversins éventuels.
    """
    F0x, F0y = pts["F0"]

    # Même logique de fin de segment que partout ailleurs (LNF v1/v2)
    x_end = pts.get("Bx_mer", pts.get("Bx", (F0x, 0)))[0]
    y_end = pts.get("By_mer", pts.get("By", (F0x, F0y)))[1]

    # On retire l’épaisseur des traversins sur les lignes concernées
    if traversins:
        if "b" in traversins:
            x_end -= TRAVERSIN_THK
        if "g" in traversins:
            y_end -= TRAVERSIN_THK

    def count_bottom(x_start, size):
        if x_end <= x_start or size <= 0:
            return 0
        return max(0, int((x_end - x_start) // size))

    def count_left(y_start, size):
        if y_end <= y_start or size <= 0:
            return 0
        return max(0, int((y_end - y_start) // size))

    best_size = 65
    # score = (surface_couverte, -déchet_total, taille)
    best_score = (-1, 0.0, 0)

    for size in (65, 80, 90):
        # Disposition A : bas collé au coin, gauche décalé vers le haut
        cbA = count_bottom(F0x, size)
        clA = count_left(F0y + CUSHION_DEPTH, size)
        nA = cbA + clA
        wasteA = 0.0
        if x_end > F0x:
            wasteA += (x_end - F0x) % size
        if y_end > (F0y + CUSHION_DEPTH):
            wasteA += (y_end - (F0y + CUSHION_DEPTH)) % size
        coverA = nA * size  # proportionnel à la surface (CUSHION_DEPTH est constant)

        # Disposition B : gauche collé au coin, bas décalé vers la droite
        cbB = count_bottom(F0x + CUSHION_DEPTH, size)
        clB = count_left(F0y, size)
        nB = cbB + clB
        wasteB = 0.0
        if x_end > (F0x + CUSHION_DEPTH):
            wasteB += (x_end - (F0x + CUSHION_DEPTH)) % size
        if y_end > F0y:
            wasteB += (y_end - F0y) % size
        coverB = nB * size

        # Pour cette taille, garder la disposition qui couvre le plus,
        # puis qui génère le moins de déchet.
        if (coverB, -wasteB) > (coverA, -wasteA):
            cover, waste = coverB, wasteB
        else:
            cover, waste = coverA, wasteA

        # Score global pour cette taille :
        # 1. plus de surface couverte
        # 2. moins de déchet
        # 3. taille plus grande en dernier recours
        score = (cover, -waste, size)
        if score > best_score:
            best_score = score
            best_size = size

    return best_size

def draw_coussins_L_optimized(t, tr, pts, coussins, traversins=None):
    if isinstance(coussins, str) and coussins.strip().lower()=="auto":
        size = _choose_cushion_size_auto_L(pts, traversins=traversins)
    else:
        size = int(coussins)

    F0x, F0y = pts["F0"]
    x_end = pts.get("Bx_mer", pts["Bx"])[0]
    y_end = pts.get("By_mer", pts["By"])[1]
    if traversins:
        if "b" in traversins: x_end -= TRAVERSIN_THK
        if "g" in traversins: y_end -= TRAVERSIN_THK

    def count_bottom(x_start): return max(0, int((x_end - x_start)//size))
    def count_left(y_start):   return max(0, int((y_end - y_start)//size))

    nA = count_bottom(F0x) + count_left(F0y + CUSHION_DEPTH)  # bas collé
    nB = count_bottom(F0x + CUSHION_DEPTH) + count_left(F0y)  # bas décalé

    def draw_bottom(x_start):
        cnt=0; y=F0y; x_cur=x_start
        while x_cur + size <= x_end + 1e-6:
            poly=[(x_cur,y),(x_cur+size,y),(x_cur+size,y+CUSHION_DEPTH),(x_cur,y+CUSHION_DEPTH),(x_cur,y)]
            draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
            label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
            x_cur += size; cnt += 1
        return cnt
    def draw_left(y_start):
        cnt=0; x=F0x; y_cur=y_start
        while y_cur + size <= y_end + 1e-6:
            poly=[(x,y_cur),(x+CUSHION_DEPTH,y_cur),(x+CUSHION_DEPTH,y_cur+size),(x,y_cur+size),(x,y_cur)]
            draw_polygon_cm(t,tr,poly,fill=COLOR_CUSHION,outline=COLOR_CONTOUR,width=1)
            label_poly(t,tr,poly,f"{size}",font=FONT_CUSHION)
            y_cur += size; cnt += 1
        return cnt

    # tie-break : max coussins, puis déchet minimal
    wasteA = (max(0, x_end-F0x)%size) + (max(0, y_end-(F0y+CUSHION_DEPTH))%size)
    wasteB = (max(0, x_end-(F0x+CUSHION_DEPTH))%size) + (max(0, y_end-F0y)%size)
    if (nB, -wasteB) > (nA, -wasteA):
        cb = draw_bottom(F0x + CUSHION_DEPTH); cl = draw_left(F0y)
        return cb + cl, size
    else:
        cb = draw_bottom(F0x); cl = draw_left(F0y + CUSHION_DEPTH)
        return cb + cl, size

def _render_common_L(tx, ty, pts, polys, coussins, window_title,
                     profondeur, dossier_left, dossier_bas, meridienne_side, meridienne_len,
                     traversins=None, couleurs=None, variant="v1"):
    _assert_banquettes_max_250(polys)

    trv = _parse_traversins_spec(traversins, allowed={"g","b"})
    legend_items = _resolve_and_apply_colors(couleurs)

    screen = turtle.Screen(); screen.setup(WIN_W,WIN_H)
    screen.title(f"{window_title} — {tx}×{ty} — prof={profondeur} — méridienne {meridienne_side or '-'}={meridienne_len} — coussins={coussins}")
    t = turtle.Turtle(visible=False); t.speed(0); screen.tracer(False)
    tr = WorldToScreen(tx, ty, WIN_W, WIN_H, PAD_PX, ZOOM)

    # (Quadrillage et repères supprimés)

    for p in polys["dossiers"]:   draw_polygon_cm(t,tr,p,fill=COLOR_DOSSIER)
    for p in polys["banquettes"]: draw_polygon_cm(t,tr,p,fill=COLOR_ASSISE)
    for p in polys["accoudoirs"]: draw_polygon_cm(t,tr,p,fill=COLOR_ACC)

    # Traversins + comptage
    n_traversins = _draw_traversins_L_like(t, tr, pts, profondeur, trv)

    draw_double_arrow_vertical_cm(t,tr,-25,0,ty,f"{ty} cm")
    draw_double_arrow_horizontal_cm(t,tr,-25,0,tx,f"{tx} cm")

    # Banquettes : afficher les dimensions sur deux lignes. Décaler légèrement lorsque la banquette est verticale.
    banquette_sizes = []
    for poly in polys["banquettes"]:
        L, P = banquette_dims(poly)
        banquette_sizes.append((L, P))
        # Afficher la longueur sans unité suivie d'un « x » puis la profondeur avec « cm »
        text = f"{L}x\n{P} cm"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Décaler horizontalement pour éloigner le texte des coussins lorsque la banquette est plus haute que large
        # Réduction de 3 cm : offset plus faible
        if bb_h >= bb_w:
            label_poly_offset_cm(t, tr, poly, text, dx_cm=CUSHION_DEPTH + 7, dy_cm=0.0)
        else:
            label_poly(t, tr, poly, text)

    # Annoter dossiers et accoudoirs avec leurs épaisseurs
    _label_backrests_armrests(t, tr, polys)

    # ===== COUSSINS =====
    spec = _parse_coussins_spec(coussins)
    # Compteurs de coussins pour le rapport détaillé
    nb_coussins_65 = 0
    nb_coussins_80 = 0
    nb_coussins_90 = 0
    nb_coussins_valise = 0
    if spec["mode"] == "auto":
        cushions_count, chosen_size = draw_coussins_L_optimized(
            t,
            tr,
            pts,
            "auto",
            traversins=trv,
        )
        total_line = f"{coussins} → {cushions_count} × {chosen_size} cm"
        # Mise à jour des compteurs pour le mode automatique
        if chosen_size == 65:
            nb_coussins_65 = cushions_count
        elif chosen_size == 80:
            nb_coussins_80 = cushions_count
        elif chosen_size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    elif spec["mode"] == "80-90":
        # Mode 80-90 : optimise séparément bas et gauche avec tailles 80 ou 90
        best = _optimize_80_90_L_like(pts, traversins=trv)
        if not best:
            raise ValueError('Aucune configuration "80-90" valide pour L.')
        sizes = best["sizes"]
        shift_bas = best["shift_bas"]
        cushions_count, sb, sg = _draw_L_like_with_sizes(
            t,
            tr,
            pts,
            sizes,
            shift_bas,
            traversins=trv,
        )
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # Mise à jour des compteurs par taille via les nombres de coussins par côté
        counts_dict = best.get("counts", best.get("eval", {}).get("counts"))
        for side, size_val in sizes.items():
            count = counts_dict.get(side, 0)
            if not count:
                continue
            if size_val == 65:
                nb_coussins_65 += count
            elif size_val == 80:
                nb_coussins_80 += count
            elif size_val == 90:
                nb_coussins_90 += count
            else:
                nb_coussins_valise += count
    elif spec["mode"] == "fixed":
        # Taille fixe : une seule dimension imposée
        cushions_count, chosen_size = draw_coussins_L_optimized(
            t,
            tr,
            pts,
            int(spec["fixed"]),
            traversins=trv,
        )
        total_line = f"{coussins} → {cushions_count} × {chosen_size} cm"
        # Mise à jour des compteurs pour le mode fixe
        if chosen_size == 65:
            nb_coussins_65 = cushions_count
        elif chosen_size == 80:
            nb_coussins_80 = cushions_count
        elif chosen_size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    else:
        # Mode valise : plage de tailles avec contrainte de delta ≤ 5 cm
        best = _optimize_valise_L_like(
            pts,
            spec["range"],
            spec["same"],
            traversins=trv,
        )
        if not best:
            raise ValueError("Aucune configuration valise valide pour L.")
        sizes = best["sizes"]
        shift_bas = best["shift_bas"]
        cushions_count, sb, sg = _draw_L_like_with_sizes(
            t,
            tr,
            pts,
            sizes,
            shift_bas,
            traversins=trv,
        )
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # En mode valise, toutes les tailles sont considérées comme valises
        nb_coussins_valise = cushions_count

    # Légende
    draw_legend(t, tr, tx, ty, items=legend_items, pos="top-right")

    screen.tracer(True); t.hideturtle()

    add_split = int(polys.get("split_flags",{}).get("left",False) and dossier_left) \
              + int(polys.get("split_flags",{}).get("bottom",False) and dossier_bas)

    print("=== Rapport LNF ===")
    print(f"Dimensions : {tx}×{ty} — prof={profondeur} — méridienne {meridienne_side or '-'}={meridienne_len}")
    print(f"Banquettes : {len(polys['banquettes'])} → {banquette_sizes}")
    # Comptage pondéré des dossiers : <=110cm → 0.5, >110cm → 1
    dossiers_count = _compute_dossiers_count(polys)
    dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    print(f"Dossiers : {dossiers_str} (+{add_split} via scission) | Accoudoirs : {len(polys['accoudoirs'])}")
    print(f"Banquettes d’angle : 0")
    print(f"Traversins : {n_traversins} × 70x20")
    print(f"Coussins : {total_line}")
    # Bloc détaillé issu des données de la console
    nb_banquettes = len(polys["banquettes"])
    nb_banquettes_angle = 0  # Un L sans angle n'a pas de banquettes d'angle
    nb_accoudoirs = len(polys["accoudoirs"])
    # Utiliser la représentation formatée pour le nombre de dossiers
    nb_dossiers_str = dossiers_str
    print()
    print("À partir des données console :")
    print(f"Dimensions : {tx}×{ty} — prof={profondeur} — méridienne {meridienne_side or '-'}={meridienne_len}")
    print(f"Nombre de banquettes : {nb_banquettes}")
    print(f"Nombre de banquette d’angle : {nb_banquettes_angle}")
    print(f"Nombre de dossiers : {nb_dossiers_str}")
    print(f"Nombre d’accoudoir : {nb_accoudoirs}")
    # Afficher également les dimensions des accoudoirs
    _print_accoudoirs_dimensions(polys)
    # Affichage des dimensions des dossiers pour les canapés en L.
    # Choix de la logique selon la variante : v1 ou v2.
    _banquette_labels = _compute_banquette_labels(polys)
    if variant == "v2":
        _print_dossiers_dimensions_LNF_v2(
            _banquette_labels,
            banquette_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            meridienne_side,
            meridienne_len,
        )
    else:
        _print_dossiers_dimensions_LNF_v1(
            _banquette_labels,
            banquette_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            meridienne_side,
            meridienne_len,
        )
    # Étiquetage des banquettes en tenant compte des scissions : numéro
    # suivi éventuellement d'un suffixe "-bis" pour les scissions
    for label, (L_b, P_b) in zip(_banquette_labels, banquette_sizes):
        print(f"Dimension mousse {label} : {L_b}, {P_b}")
    print(f"Nombre de coussins 65cm : {nb_coussins_65}")
    print(f"Nombre de coussins 80cm : {nb_coussins_80}")
    print(f"Nombre de coussins 90cm : {nb_coussins_90}")
    print(f"Nombre de coussins valises total : {nb_coussins_valise}")
    print(f"Nombre de traversin : {n_traversins}")
    turtle.done()

def render_LNF_v1(tx, ty, profondeur=DEPTH_STD,
                  dossier_left=True, dossier_bas=True,
                  acc_left=True, acc_bas=True,
                  meridienne_side=None, meridienne_len=0,
                  coussins="auto",
                  traversins=None,
                  couleurs=None,
                  window_title="LNF v1 — pivot gauche"):
    if meridienne_side=='g':
        if acc_left: raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
        if not dossier_left: raise ValueError("Méridienne gauche impossible sans dossier gauche.")
    if meridienne_side=='b':
        if acc_bas: raise ValueError("Méridienne bas interdite avec accoudoir bas.")
        if not dossier_bas: raise ValueError("Méridienne bas impossible sans dossier bas.")
    pts = compute_points_LNF_v1(tx,ty,profondeur,dossier_left,dossier_bas,acc_left,acc_bas,meridienne_side,meridienne_len)
    polys = build_polys_LNF_v1(pts,tx,ty,profondeur,dossier_left,dossier_bas,acc_left,acc_bas,meridienne_side,meridienne_len)
    _render_common_L(tx, ty, pts, polys, coussins, window_title, profondeur, dossier_left, dossier_bas, meridienne_side, meridienne_len, traversins=traversins, couleurs=couleurs, variant="v1")

def render_LNF_v2(tx, ty, profondeur=DEPTH_STD,
                  dossier_left=True, dossier_bas=True,
                  acc_left=True, acc_bas=True,
                  meridienne_side=None, meridienne_len=0,
                  coussins="auto",
                  traversins=None,
                  couleurs=None,
                  window_title="LNF v2 — pivot bas"):
    if meridienne_side=='g':
        if acc_left: raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
        if not dossier_left: raise ValueError("Méridienne gauche impossible sans dossier gauche.")
    if meridienne_side=='b':
        if acc_bas: raise ValueError("Méridienne bas interdite avec accoudoir bas.")
        if not dossier_bas: raise ValueError("Méridienne bas impossible sans dossier bas.")
    pts = compute_points_LNF_v2(tx,ty,profondeur,dossier_left,dossier_bas,acc_left,acc_bas,meridienne_side,meridienne_len)
    polys = build_polys_LNF_v2(pts,tx,ty,profondeur,dossier_left,dossier_bas,acc_left,acc_bas,meridienne_side,meridienne_len)
    _render_common_L(tx, ty, pts, polys, coussins, window_title, profondeur, dossier_left, dossier_bas, meridienne_side, meridienne_len, traversins=traversins, couleurs=couleurs, variant="v2")

def _dry_polys_for_variant(tx, ty, profondeur,
                           dossier_left, dossier_bas,
                           acc_left, acc_bas,
                           meridienne_side, meridienne_len,
                           variant):
    if meridienne_side == 'g':
        if acc_left:        raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
        if not dossier_left:raise ValueError("Méridienne gauche impossible sans dossier gauche.")
    if meridienne_side == 'b':
        if acc_bas:         raise ValueError("Méridienne bas interdite avec accoudoir bas.")
        if not dossier_bas: raise ValueError("Méridienne bas impossible sans dossier bas.")

    if variant == "v1":
        pts = compute_points_LNF_v1(tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas, meridienne_side, meridienne_len)
        polys = build_polys_LNF_v1(pts, tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas, meridienne_side, meridienne_len)
    else:
        pts = compute_points_LNF_v2(tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas, meridienne_side, meridienne_len)
        polys = build_polys_LNF_v2(pts, tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas, meridienne_side, meridienne_len)
    return pts, polys

def render_LNF(tx, ty, profondeur=DEPTH_STD,
               dossier_left=True, dossier_bas=True,
               acc_left=True, acc_bas=True,
               meridienne_side=None, meridienne_len=0,
               coussins="auto",
               variant="auto",
               traversins=None,
               couleurs=None,
               window_title="LNF — auto"):
    if variant and variant.lower() in ("v1", "v2"):
        chosen = variant.lower()
        if chosen == "v2":
            render_LNF_v2(tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas,
                          meridienne_side, meridienne_len, coussins, traversins=traversins, couleurs=couleurs,
                          window_title=window_title)
        else:
            render_LNF_v1(tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas,
                          meridienne_side, meridienne_len, coussins, traversins=traversins, couleurs=couleurs,
                          window_title=window_title)
        return

    nb_ban_v1 = float("inf")
    nb_ban_v2 = float("inf")
    polys1 = polys2 = None
    try:
        _pts1, _polys1 = _dry_polys_for_variant(tx, ty, profondeur,
                                               dossier_left, dossier_bas,
                                               acc_left, acc_bas,
                                               meridienne_side, meridienne_len,
                                               "v1")
        nb_ban_v1 = len(_polys1["banquettes"]); polys1=_polys1
    except ValueError:
        pass
    try:
        _pts2, _polys2 = _dry_polys_for_variant(tx, ty, profondeur,
                                               dossier_left, dossier_bas,
                                               acc_left, acc_bas,
                                               meridienne_side, meridienne_len,
                                               "v2")
        nb_ban_v2 = len(_polys2["banquettes"]); polys2=_polys2
    except ValueError:
        pass

    # choix : moins de banquettes ; tie-break = moins de scissions
    def scissions(polys):
        if not polys: return 999
        base_groups = 2  # L = gauche + bas
        return max(0, len(polys["banquettes"]) - base_groups)
    if nb_ban_v1 < nb_ban_v2: chosen = "v1"
    elif nb_ban_v2 < nb_ban_v1: chosen = "v2"
    else:
        if scissions(polys1) < scissions(polys2): chosen="v1"
        elif scissions(polys2) < scissions(polys1): chosen="v2"
        else: chosen = "v1" if tx >= ty else "v2"

    if chosen == "v2":
        render_LNF_v2(tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas,
                      meridienne_side, meridienne_len, coussins, traversins=traversins, couleurs=couleurs,
                      window_title=window_title)
    else:
        render_LNF_v1(tx, ty, profondeur, dossier_left, dossier_bas, acc_left, acc_bas,
                      meridienne_side, meridienne_len, coussins, traversins=traversins, couleurs=couleurs,
                      window_title=window_title)

# =====================================================================
# =====================  U (no fromage) — v1..v4  =====================
# =====================================================================

def compute_points_U_v1(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Compute the key geometry points for a U‑shaped sofa variant v1,
    optionally including a méridienne. When ``meridienne_side`` is 'g'
    (left) or 'd' (right) and ``meridienne_len`` > 0, the corresponding
    branch's back height is reduced accordingly. Additional keys
    ``By_`` and/or ``By4_`` are created to record these reduced heights.

    Parameters
    ----------
    tx, ty_left, tz_right : int
        Dimensions of the sofa (overall width and branch heights).
    profondeur : int
        Depth of the seat.
    dossier_left, dossier_bas, dossier_right : bool
        Flags indicating presence of backs on the left, bottom and right.
    acc_left, acc_bas, acc_right : bool
        Flags indicating presence of armrests on the left, bottom and right.
    meridienne_side : {'g', 'd', None}
        Side on which a méridienne is present ('g' for left, 'd' for right).
    meridienne_len : int
        Length of the méridienne; ignored if non‑positive or ``meridienne_side`` is None.

    Returns
    -------
    dict
        A dictionary of named points used to build the sofa's geometry.
    """
    prof = profondeur
    pts = {}
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas else 0
    pts["D0"] = (0, 0)
    pts["D0x"] = (F0x, 0)
    pts["D0y"] = (0, F0y)
    pts["F0"] = (F0x, F0y)

    # Left branch geometry
    pts["Dy"] = (0, F0y + prof)
    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos = (
        max(F0y + prof, top_y_L_full - meridienne_len)
        if (meridienne_side == "g" and meridienne_len > 0)
        else top_y_L_full
    )
    pts["Dy2"] = (0, top_y_L_dos)
    pts["Ay"] = (0, ty_left)
    pts["Ay2"] = (F0x + prof, ty_left)
    pts["Ay_"] = (F0x, ty_left)

    pts["Fy"] = (F0x, F0y + prof)
    pts["Fy2"] = (F0x + prof, F0y + prof)
    pts["By"] = (F0x, top_y_L_full)
    pts["By2"] = (F0x + prof, top_y_L_full)
    if meridienne_side == "g" and meridienne_len > 0:
        # Reduced height points for méridienne on left
        pts["By_"] = (pts["By"][0], top_y_L_dos)
        pts["By2_"] = (pts["By2"][0], top_y_L_dos)

    # Right branch above the bottom
    D02x_x = tx - (10 if (dossier_right or dossier_bas) else 0)
    pts["Dx"] = (F0x + prof, 0)
    pts["Bx"] = (D02x_x, F0y)
    pts["Bx2"] = (D02x_x, F0y + prof)

    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    x_left_R = D02x_x - prof
    pts["Fy3"] = (x_left_R, F0y + prof)
    pts["By3"] = (x_left_R, top_y_R_full)
    pts["By4"] = (D02x_x, top_y_R_full)

    top_y_R_dos = (
        max(F0y + prof, top_y_R_full - meridienne_len)
        if (meridienne_side == "d" and meridienne_len > 0)
        else top_y_R_full
    )
    pts["D02x"] = (D02x_x, 0)
    pts["D02"] = (tx, 0)
    pts["D02y"] = (tx, F0y)
    pts["Dy3"] = (tx, top_y_R_dos)
    if meridienne_side == "d" and meridienne_len > 0:
        # Reduced height point for méridienne on right
        pts["By4_"] = (pts["By4"][0], top_y_R_dos)

    pts["Ax"] = (x_left_R, tz_right)
    pts["Ax2"] = (tx, tz_right)
    pts["Ax_par"] = (D02x_x, tz_right)

    # Canvas height for drawing
    pts["_ty_canvas"] = max(ty_left, tz_right)
    return pts

def build_polys_U_v1(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                     dossier_left=True, dossier_bas=True, dossier_right=True,
                     acc_left=True, acc_bas=True, acc_right=True):
    polys={"banquettes":[],"dossiers":[],"accoudoirs":[]}

    draw = {
        "D1": bool(dossier_left),
        "D2": bool(dossier_left or dossier_bas),
        "D3": bool(dossier_bas),
        "D4": bool(dossier_right),              # v1 : uniquement dossier_droit
        "D5": bool(dossier_right),
    }

    F0=pts["F0"]; Fy=pts["Fy"]; Fy2=pts["Fy2"]; By=pts["By"]; By2=pts["By2"]
    Bx=pts["Bx"]; Bx2=pts["Bx2"]; Fy3=pts["Fy3"]; By3=pts["By3"]; By4=pts["By4"]

    # banquettes
    split_left=split_bottom=split_right=False
    ban_g=[Fy,By,By2,Fy2,Fy]
    Lg=abs(By[1]-Fy[1])
    if Lg>SPLIT_THRESHOLD:
        split_left=True
        mid_y=_split_mid_int(Fy[1],By[1])
        g_low=[(Fy[0],Fy[1]),(Fy2[0],Fy[1]),(Fy2[0],mid_y),(Fy[0],mid_y),(Fy[0],Fy[1])]
        g_up=[(Fy[0],mid_y),(By[0],By[1]),(By2[0],By2[1]),(Fy2[0],mid_y),(Fy[0],mid_y)]
        polys["banquettes"]+=[g_low,g_up]
    else:
        polys["banquettes"].append(ban_g)

    ban_b=[F0,Bx,Bx2,Fy,F0]
    Lb=abs(Bx[0]-F0[0])
    if Lb>SPLIT_THRESHOLD:
        split_bottom=True
        mid_x=_split_mid_int(F0[0],Bx[0])
        b_left=[(F0[0],F0[1]),(mid_x,F0[1]),(mid_x,Fy[1]),(Fy[0],Fy[1]),(F0[0],F0[1])]
        b_right=[(mid_x,F0[1]),(Bx[0],Bx[1]),(Bx2[0],Bx2[1]),(mid_x,Fy[1]),(mid_x,F0[1])]
        polys["banquettes"]+=[b_left,b_right]
    else:
        polys["banquettes"].append(ban_b)

    ban_r=[By3,By4,Bx2,Fy3,By3]
    Lr=abs(By4[1]-Fy3[1])
    if Lr>SPLIT_THRESHOLD:
        split_right=True
        mid_y=_split_mid_int(Fy3[1],By4[1])
        r_low=[(Fy3[0],Fy3[1]),(Bx2[0],Fy3[1]),(Bx2[0],mid_y),(Fy3[0],mid_y),(Fy3[0],Fy3[1])]
        r_up=[(Fy3[0],mid_y),(By3[0],By3[1]),(By4[0],By4[1]),(Bx2[0],mid_y),(Fy3[0],mid_y)]
        polys["banquettes"]+=[r_low,r_up]
    else:
        polys["banquettes"].append(ban_r)

    # dossiers (groupes par côtés)
    groups = _dossiers_groups_U("v1", pts, tx, profondeur, draw)
    _append_groups_to_polys_U(polys, groups)

    # Accoudoirs U v1
    if acc_left:
        if draw["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])
    if acc_right:
        if draw["D5"]:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], pts["Dy3"], pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    polys["split_flags"]={"left":split_left,"bottom":split_bottom,"right":split_right}
    return polys, draw

def compute_points_U_v2(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Compute the key geometry points for a U‑shaped sofa variant v2,
    including optional méridienne support. Variant v2 has the left branch
    aligned with the bottom. When a méridienne is specified on either
    side, the branch height is reduced and additional keys ``By_`` or
    ``By4_`` are created to hold the reduced heights.

    See ``compute_points_U_v1`` for parameter descriptions.
    """
    prof = profondeur
    pts = {}
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas else 0
    pts["D0"] = (0, 0)
    pts["D0x"] = (F0x, 0)
    pts["D0y"] = (0, F0y)
    pts["F0"] = (F0x, F0y)

    # Left branch (Fy at the bottom)
    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos = (
        max(F0y + prof, top_y_L_full - meridienne_len)
        if (meridienne_side == "g" and meridienne_len > 0)
        else top_y_L_full
    )
    pts["Dy2"] = (0, top_y_L_dos)
    pts["Ay"] = (0, ty_left)
    pts["Ay2"] = (F0x + prof, ty_left)
    pts["Ay_"] = (F0x, ty_left)
    pts["Fy"] = (F0x, F0y)
    pts["Fy2"] = (F0x + prof, F0y)
    pts["Fx"] = (F0x + prof, F0y)
    pts["Fx2"] = (F0x + prof, F0y + prof)
    pts["By"] = (F0x, top_y_L_full)
    pts["By2"] = (F0x + prof, top_y_L_full)
    if meridienne_side == "g" and meridienne_len > 0:
        pts["By_"] = (pts["By"][0], top_y_L_dos)
        pts["By2_"] = (pts["By2"][0], top_y_L_dos)

    # Bottom part up to Dx2
    D02x_x = tx - (10 if (dossier_right or dossier_bas) else 0)
    Dx2_x = D02x_x - prof
    pts["Dx"] = (F0x + prof, 0)
    pts["Dx2"] = (Dx2_x, 0)
    pts["Bx"] = (Dx2_x, F0y)
    pts["Bx2"] = (Dx2_x, F0y + prof)

    # Right branch (to the right of the bottom)
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    pts["F02"] = (D02x_x, F0y)
    pts["By4"] = (D02x_x, top_y_R_full)
    pts["By3"] = (Dx2_x, top_y_R_full)
    top_y_R_dos = (
        max(F0y + prof, top_y_R_full - meridienne_len)
        if (meridienne_side == "d" and meridienne_len > 0)
        else top_y_R_full
    )
    pts["D02x"] = (D02x_x, 0)
    pts["D02"] = (tx, 0)
    pts["D02y"] = (tx, F0y)
    pts["Dy3"] = (tx, top_y_R_dos)
    if meridienne_side == "d" and meridienne_len > 0:
        pts["By4_"] = (pts["By4"][0], top_y_R_dos)

    pts["Ax"] = (Dx2_x, tz_right)
    pts["Ax2"] = (tx, tz_right)
    pts["Ax_par"] = (D02x_x, tz_right)
    # Store the exact right banquette split height for backrest scission.
    # For variant v2 the right banquette spans vertically from the y of
    # ``F02`` (the bottom of the right branch) to the y of ``By3`` (the top of
    # the right seat).  Using these values exactly ensures the backrest
    # scission aligns perfectly with the banquette scission.
    seat_y0_right = pts["F02"][1]  # bottom of the right banquette
    # The top of the right banquette is given by By3 (same as By4 on y)
    seat_y1_right = pts["By4"][1]
    pts["__SPLIT_Y_RIGHT"] = 0.5 * (seat_y0_right + seat_y1_right)

    pts["_ty_canvas"] = max(ty_left, tz_right)
    return pts

def build_polys_U_v2(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                     dossier_left=True, dossier_bas=True, dossier_right=True,
                     acc_left=True, acc_bas=True, acc_right=True):
    polys={"banquettes":[],"dossiers":[],"accoudoirs":[]}

    draw = {
        "D1": bool(dossier_left),
        "D2": bool(dossier_left or dossier_bas),
        "D3": bool(dossier_bas),
        "D4": bool(dossier_right or dossier_bas),
        "D5": bool(dossier_right),
    }

    F0=pts["F0"]; Fy=pts["Fy"]; Fx=pts["Fx"]; Fx2=pts["Fx2"]; By=pts["By"]; By2=pts["By2"]
    Bx=pts["Bx"]; Bx2=pts["Bx2"]; By3=pts["By3"]; By4=pts["By4"]; F02=pts["F02"]

    split_left=split_bottom=split_right=False

    # banquettes
    ban_g=[F0,By,By2,Fx,F0]
    Lg=abs(By[1]-F0[1])
    if Lg>SPLIT_THRESHOLD:
        split_left=True
        mid_y=_split_mid_int(F0[1],By[1])
        g_low=[(F0[0],F0[1]),(Fx[0],F0[1]),(Fx[0],mid_y),(F0[0],mid_y),(F0[0],F0[1])]
        g_up=[(F0[0],mid_y),(By[0],By[1]),(By2[0],By2[1]),(Fx[0],mid_y),(F0[0],mid_y)]
        polys["banquettes"]+=[g_low,g_up]
    else:
        polys["banquettes"].append(ban_g)

    ban_b=[Fx,Bx,Bx2,Fx2,Fx]
    Lb=abs(Bx2[0]-Fx2[0])
    if Lb>SPLIT_THRESHOLD:
        split_bottom=True
        mid_x=_split_mid_int(Fx2[0],Bx2[0])
        b_left=[(Fx[0],Fx[1]),(mid_x,Fx[1]),(mid_x,Fx2[1]),(Fx2[0],Fx2[1]),(Fx[0],Fx[1])]
        b_right=[(mid_x,Fx[1]),(Bx[0],Bx[1]),(Bx2[0],Bx2[1]),(mid_x,Fx2[1]),(mid_x,Fx[1])]
        polys["banquettes"]+=[b_left,b_right]
    else:
        polys["banquettes"].append(ban_b)

    ban_r=[F02,By4,By3,Bx,F02]
    Lr=abs(By3[1]-F02[1])
    if Lr>SPLIT_THRESHOLD:
        split_right=True
        mid_y=_split_mid_int(F02[1],By3[1])
        # Use the exact split height from the banquette for the right backrest
        pts["__SPLIT_Y_RIGHT"] = mid_y
        r_low=[(Bx[0],mid_y),(Bx[0],F02[1]),(F02[0],F02[1]),(F02[0],mid_y),(Bx[0],mid_y)]
        r_up=[(Bx[0],mid_y),(By3[0],By3[1]),(By4[0],By4[1]),(F02[0],mid_y),(Bx[0],mid_y)]
        polys["banquettes"]+=[r_low,r_up]
    else:
        # No split: still compute the median as potential split height
        pts["__SPLIT_Y_RIGHT"] = 0.5 * (F02[1] + By3[1])
        polys["banquettes"].append(ban_r)

    # dossiers
    groups = _dossiers_groups_U("v2", pts, tx, profondeur, draw)
    _append_groups_to_polys_U(polys, groups)

    # Accoudoirs U v2
    if acc_left:
        if draw["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])
    if acc_right:
        if draw["D5"]:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], pts["Dy3"], pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    polys["split_flags"]={"left":split_left,"bottom":split_bottom,"right":split_right}
    return polys, draw

def compute_points_U_v3(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Compute the key geometry points for a U‑shaped sofa variant v3,
    including optional méridienne support. Variant v3 is similar to v1
    but with different layout. As with other variants, specifying a
    méridienne reduces the corresponding branch height and adds ``By_``
    or ``By4_`` keys.

    See ``compute_points_U_v1`` for parameter descriptions.
    """
    prof = profondeur
    pts = {}
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas else 0
    pts["D0"] = (0, 0)
    pts["D0x"] = (F0x, 0)
    pts["D0y"] = (0, F0y)
    pts["F0"] = (F0x, F0y)

    # Left branch (similar to v1)
    pts["Dy"] = (0, F0y + prof)
    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    top_y_L_dos = (
        max(F0y + prof, top_y_L_full - meridienne_len)
        if (meridienne_side == "g" and meridienne_len > 0)
        else top_y_L_full
    )
    pts["Dy2"] = (0, top_y_L_dos)
    pts["Ay"] = (0, ty_left)
    pts["Ay2"] = (F0x + prof, ty_left)
    pts["Ay_"] = (F0x, ty_left)
    pts["Fy"] = (F0x, F0y + prof)
    pts["Fy2"] = (F0x + prof, F0y + prof)
    pts["By"] = (F0x, top_y_L_full)
    pts["By2"] = (F0x + prof, top_y_L_full)
    if meridienne_side == "g" and meridienne_len > 0:
        pts["By_"] = (pts["By"][0], top_y_L_dos)
        pts["By2_"] = (pts["By2"][0], top_y_L_dos)

    # Bottom up to Bx (= D02x - prof)
    D02x_x = tx - (10 if (dossier_right or dossier_bas) else 0)
    Bx_x = D02x_x - prof
    pts["Dx"] = (F0x + prof, 0)
    pts["Bx"] = (Bx_x, F0y)
    pts["Bx2"] = (Bx_x, F0y + prof)

    # Right branch (to the right of the bottom)
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    pts["By3"] = (Bx_x, top_y_R_full)
    pts["F02"] = (D02x_x, F0y)
    pts["By4"] = (D02x_x, top_y_R_full)
    top_y_R_dos = (
        max(F0y + prof, top_y_R_full - meridienne_len)
        if (meridienne_side == "d" and meridienne_len > 0)
        else top_y_R_full
    )
    pts["D02x"] = (D02x_x, 0)
    pts["D02"] = (tx, 0)
    pts["D02y"] = (tx, F0y)
    pts["Dy3"] = (tx, top_y_R_dos)
    if meridienne_side == "d" and meridienne_len > 0:
        pts["By4_"] = (pts["By4"][0], top_y_R_dos)

    pts["Ax"] = (Bx_x, tz_right)
    pts["Ax2"] = (tx, tz_right)
    pts["Ax_par"] = (D02x_x, tz_right)
    # Store the exact right banquette split height for backrest scission.
    # For variant v3 the right banquette spans from ``F02.y`` (the bottom
    # of the right branch) to ``By3.y`` (the top of the right seat).  Using
    # these values ensures the backrest scission aligns perfectly with the
    # banquette scission.
    seat_y0_right = pts["F02"][1]
    seat_y1_right = pts["By4"][1]  # By4 and By3 share the same y
    pts["__SPLIT_Y_RIGHT"] = 0.5 * (seat_y0_right + seat_y1_right)

    pts["_ty_canvas"] = max(ty_left, tz_right)
    return pts

def build_polys_U_v3(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                     dossier_left=True, dossier_bas=True, dossier_right=True,
                     acc_left=True, acc_bas=True, acc_right=True):
    polys={"banquettes":[],"dossiers":[],"accoudoirs":[]}

    draw = {
        "D1": bool(dossier_left),
        "D2": bool(dossier_left or dossier_bas),
        "D3": bool(dossier_bas),
        "D4": bool(dossier_right or dossier_bas),
        "D5": bool(dossier_right),
    }

    F0=pts["F0"]; Fy=pts["Fy"]; Fy2=pts["Fy2"]; By=pts["By"]; By2=pts["By2"]
    Bx=pts["Bx"]; Bx2=pts["Bx2"]; By3=pts["By3"]; By4=pts["By4"]; F02=pts["F02"]

    split_left=split_bottom=split_right=False
    # banquettes
    ban_g=[Fy,By,By2,Fy2,Fy]
    Lg=abs(By[1]-Fy[1])
    if Lg>SPLIT_THRESHOLD:
        split_left=True
        mid_y=_split_mid_int(Fy[1],By[1])
        g_low=[(Fy[0],Fy[1]),(Fy2[0],Fy[1]),(Fy2[0],mid_y),(Fy[0],mid_y),(Fy[0],Fy[1])]
        g_up=[(Fy[0],mid_y),(By[0],By[1]),(By2[0],By2[1]),(Fy2[0],mid_y),(Fy[0],mid_y)]
        polys["banquettes"]+=[g_low,g_up]
    else:
        polys["banquettes"].append(ban_g)

    ban_b=[F0,Bx,Bx2,Fy,F0]
    Lb=abs(Bx[0]-F0[0])
    if Lb>SPLIT_THRESHOLD:
        split_bottom=True
        mid_x=_split_mid_int(F0[0],Bx[0])
        b_left=[(F0[0],F0[1]),(mid_x,F0[1]),(mid_x,Fy[1]),(Fy[0],Fy[1]),(F0[0],F0[1])]
        b_right=[(mid_x,F0[1]),(Bx[0],Bx[1]),(Bx2[0],Bx2[1]),(mid_x,Fy[1]),(mid_x,F0[1])]
        polys["banquettes"]+=[b_left,b_right]
    else:
        polys["banquettes"].append(ban_b)

    # droite : By3 - By4 - F02 - Bx - By3
    ban_r=[By3,By4,F02,Bx,By3]
    Lr=abs(By3[1]-F02[1])
    if Lr>SPLIT_THRESHOLD:
        split_right=True
        mid_y=_split_mid_int(F02[1],By3[1])
        # Use the exact split height from the banquette for the right backrest
        pts["__SPLIT_Y_RIGHT"] = mid_y
        r_low=[(Bx[0],F02[1]),(F02[0],F02[1]),(F02[0],mid_y),(Bx[0],mid_y),(Bx[0],F02[1])]
        r_up=[(Bx[0],mid_y),(By3[0],By3[1]),(By4[0],By4[1]),(F02[0],mid_y),(Bx[0],mid_y)]
        polys["banquettes"]+=[r_low,r_up]
    else:
        # No split: still compute the median as potential split height
        pts["__SPLIT_Y_RIGHT"] = 0.5 * (F02[1] + By3[1])
        polys["banquettes"].append(ban_r)

    # dossiers
    groups = _dossiers_groups_U("v3", pts, tx, profondeur, draw)
    _append_groups_to_polys_U(polys, groups)

    # Accoudoirs U v3
    if acc_left:
        if draw["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])
    if acc_right:
        if draw["D5"]:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], pts["Dy3"], pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    polys["split_flags"]={"left":split_left,"bottom":split_bottom,"right":split_right}
    return polys, draw

def compute_points_U_v4(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Compute the key geometry points for a U‑shaped sofa variant v4,
    including optional méridienne support. Variant v4 has a particular
    arrangement of the left and right branches. When a méridienne is
    specified, the back height on that side is reduced, and keys
    ``By_`` and/or ``By4_`` are added as appropriate.

    See ``compute_points_U_v1`` for parameter descriptions.
    """
    prof = profondeur
    pts = {}
    F0x = 10 if dossier_left else 0
    F0y = 10 if dossier_bas else 0
    pts["D0"] = (0, 0)
    pts["D0x"] = (F0x, 0)
    pts["D0y"] = (0, F0y)
    pts["F0"] = (F0x, F0y)

    # Left post (montant gauche)
    top_y_L_full = ty_left - (ACCOUDOIR_THICK if acc_left else 0)
    pts["By"] = (F0x, top_y_L_full)
    pts["Fx"] = (F0x + profondeur, F0y)
    pts["Fx2"] = (F0x + profondeur, F0y + prof)
    pts["By2"] = (F0x + profondeur, top_y_L_full)
    top_y_L_dos = (
        max(F0y + prof, top_y_L_full - meridienne_len)
        if (meridienne_side == "g" and meridienne_len > 0)
        else top_y_L_full
    )
    pts["Dy2"] = (0, top_y_L_dos)
    if meridienne_side == "g" and meridienne_len > 0:
        pts["By_"] = (pts["By"][0], top_y_L_dos)
        pts["By2_"] = (pts["By2"][0], top_y_L_dos)
    pts["Ay"] = (0, ty_left)
    pts["Ay2"] = (F0x + profondeur, ty_left)
    pts["Ay_"] = (F0x, ty_left)

    # Right limit
    D02x_x = tx - (10 if (dossier_right or dossier_bas) else 0)
    pts["Dx"] = (F0x + profondeur, 0)
    pts["Bx"] = (D02x_x, F0y)
    pts["Bx2"] = (D02x_x, F0y + prof)

    # Right branch (above the bottom)
    top_y_R_full = tz_right - (ACCOUDOIR_THICK if acc_right else 0)
    x_left_R = D02x_x - prof
    pts["Fy3"] = (x_left_R, F0y + prof)
    pts["By3"] = (x_left_R, top_y_R_full)
    pts["By4"] = (D02x_x, top_y_R_full)
    top_y_R_dos = (
        max(F0y + prof, top_y_R_full - meridienne_len)
        if (meridienne_side == "d" and meridienne_len > 0)
        else top_y_R_full
    )
    pts["D02x"] = (D02x_x, 0)
    pts["D02"] = (tx, 0)
    pts["D02y"] = (tx, F0y)
    pts["Dy3"] = (tx, top_y_R_dos)
    if meridienne_side == "d" and meridienne_len > 0:
        pts["By4_"] = (pts["By4"][0], top_y_R_dos)

    pts["Ax"] = (x_left_R, tz_right)
    pts["Ax2"] = (tx, tz_right)
    pts["Ax_par"] = (D02x_x, tz_right)

    pts["_ty_canvas"] = max(ty_left, tz_right)
    return pts

def build_polys_U_v4(pts, tx, ty_left, tz_right, profondeur=DEPTH_STD,
                     dossier_left=True, dossier_bas=True, dossier_right=True,
                     acc_left=True, acc_bas=True, acc_right=True):
    polys = {"banquettes": [], "dossiers": [], "accoudoirs": []}

    draw = {
        "D1": bool(dossier_left),
        "D2": bool(dossier_left or dossier_bas),
        "D3": bool(dossier_bas),
        "D4": bool(dossier_right or dossier_bas),
        "D5": bool(dossier_right),
    }

    F0=pts["F0"]; Fx=pts["Fx"]; Fx2=pts["Fx2"]; By=pts["By"]; By2=pts["By2"]
    Bx=pts["Bx"]; Bx2=pts["Bx2"]; Fy3=pts["Fy3"]; By3=pts["By3"]; By4=pts["By4"]

    split_left=split_bottom=split_right=False

    # banquettes
    ban_g = [F0, By, By2, Fx, F0]
    Lg = abs(By[1] - F0[1])
    if Lg > SPLIT_THRESHOLD:
        split_left=True
        mid_y = _split_mid_int(F0[1], By[1])
        g_low  = [(F0[0],F0[1]), (Fx[0],F0[1]), (Fx[0],mid_y), (F0[0],mid_y), (F0[0],F0[1])]
        g_high = [(F0[0],mid_y), (By[0],By[1]), (By2[0],By2[1]), (Fx[0],mid_y), (F0[0],mid_y)]
        polys["banquettes"] += [g_low, g_high]
    else:
        polys["banquettes"].append(ban_g)

    ban_b = [Fx, Bx, Bx2, Fx2, Fx]
    Lb = abs(Bx2[0] - Fx2[0])
    if Lb > SPLIT_THRESHOLD:
        split_bottom=True
        mid_x = _split_mid_int(Fx2[0], Bx2[0])
        pts["__SPLIT_X_BOTTOM"] = mid_x
        b_left  = [(Fx[0],Fx[1]), (mid_x,Fx[1]), (mid_x,Fx2[1]), (Fx2[0],Fx2[1]), (Fx[0],Fx[1])]
        b_right = [(mid_x,Fx[1]), (Bx[0],Bx[1]), (Bx2[0],Bx2[1]), (mid_x,Fx2[1]), (mid_x,Fx[1])]
        polys["banquettes"] += [b_left, b_right]
    else:
        polys["banquettes"].append(ban_b)

    ban_r = [Fy3, By3, By4, Bx2, Fy3]
    Lr = abs(By3[1] - Fy3[1])
    if Lr > SPLIT_THRESHOLD:
        split_right=True
        mid_y = _split_mid_int(Fy3[1], By3[1])
        r_low  = [(Fy3[0],Fy3[1]), (Bx2[0],Fy3[1]), (Bx2[0],mid_y), (Fy3[0],mid_y), (Fy3[0],Fy3[1])]
        r_high = [(Fy3[0],mid_y), (By3[0],By3[1]), (By4[0],By4[1]), (Bx2[0],mid_y), (Fy3[0],mid_y)]
        polys["banquettes"] += [r_low, r_high]
    else:
        polys["banquettes"].append(ban_r)

    # dossiers
    groups = _dossiers_groups_U("v4", pts, tx, profondeur, draw)
    _append_groups_to_polys_U(polys, groups)

    # Accoudoirs U v4
    if acc_left:
        if draw["D1"]:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By2"], pts["Dy2"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay_"], pts["Ay2"], pts["By2"], pts["By"], pts["Ay_"]])
    if acc_right:
        if draw["D5"]:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax2"], pts["Dy3"], pts["By3"]])
        else:
            polys["accoudoirs"].append([pts["By3"], pts["Ax"], pts["Ax_par"], pts["By4"], pts["By3"]])

    polys["split_flags"]={"left":split_left,"bottom":split_bottom,"right":split_right}
    return polys, draw

# ---------- Dossiers par côtés (U) ----------
def _dossiers_groups_U(variant, pts, tx, profondeur, draw):
    """
    Build the groups of polygons for the backs (dossiers) of a U‑shaped sofa.

    This version honours ``By_`` and ``By4_`` when present, so that the
    dossier height is limited by the méridienne. Each group is a dict of
    lists keyed by the back segment (left D1/D2, bottom D3, right D4/D5).
    """
    groups = {
        "left": {"D1": [], "D2": []},
        "bottom": {"D3": []},
        "right": {"D4": [], "D5": []},
    }
    F0x, F0y = pts["F0"]

    By_use = pts.get("By_", pts.get("By"))
    By4_use = pts.get("By4_", pts.get("By4"))

    if variant == "v1":
        if draw["D1"]:
            # D1 gauche — rectangle(s) vertical(aux) avec scission alignée sur la banquette gauche
            x0, x1 = 0, F0x
            # portion de dossier au-dessus de l'assise : de Fy.y jusqu'à By_use.y
            y0, y1 = pts["Fy"][1], By_use[1]
            # bornes complètes de l'assise gauche pour calculer la scission (Fy.y → By.y)
            seat_y0, seat_y1 = pts["Fy"][1], pts["By"][1]
            groups["left"]["D1"] += _build_dossier_vertical_rects(x0, x1, y0, y1, seat_y0, seat_y1)
        if draw["D2"]:
            groups["left"]["D2"].append([
                pts["D0x"],
                pts["D0"],
                pts["Dy"],
                pts["Fy"],
                pts["D0x"],
            ])
        if draw["D3"]:
            F0x, F0y = pts["F0"]; xL = F0x; xR = pts["Bx"][0]
            if abs(xR - xL) > SPLIT_THRESHOLD:
                mid_x = _split_mid_int(xL, xR)
                groups["bottom"]["D3"] += [
                    _rectU(xL, 0, mid_x, F0y),
                    _rectU(mid_x, 0, xR,  F0y),
                ]
            else:
                groups["bottom"]["D3"].append(_rectU(xL, 0, xR, F0y))
        if draw["D4"]:
            groups["right"]["D4"].append([
                pts["D02x"],
                pts["D02"],
                pts["Dy3"],
                pts["Bx2"],
                pts["D02x"],
            ])
        if draw["D5"]:
            # D5 droite — rectangle(s) vertical(aux) avec scission alignée sur la banquette droite
            x0 = pts["D02x"][0]
            y1 = F0y + profondeur
            y_top = By4_use[1]
            # Utilise les bornes de l'assise droite pour déterminer la scission (Fy3.y → By4_use.y)
            groups["right"]["D5"] += _build_dossier_vertical_rects(
                x0, tx, y1, y_top,
                pts["Fy3"][1], By4_use[1]
            )

    elif variant == "v2":
        if draw["D1"]:
            # D1 gauche — scission alignée sur la banquette gauche
            x0, x1 = 0, F0x
            # inclut la lame basse : zone 0 → By_use.y
            y0, y1 = 0, By_use[1]
            seat_y0, seat_y1 = pts["Fy"][1], pts["By"][1]
            groups["left"]["D1"] += _build_dossier_vertical_rects(
                x0, x1, y0, y1,
                seat_y0, seat_y1
            )
        if draw["D2"]:
            groups["left"]["D2"].append([
                pts["D0x"],
                pts["Dx"],
                pts["Fx"],
                pts["F0"],
                pts["D0x"],
            ])
        if draw["D3"]:
            # Clip the bottom backrest so it does not overlap the left vertical backrest.
            F0x, F0y = pts["F0"]
            # Left limit starts at the right edge of the left banquette (Fx.x)
            x_left_limit = pts["Fx"][0] if "Fx" in pts else F0x
            # Right limit ends at the left edge of the right banquette (F02.x) if present
            x_right_limit = pts["F02"][0] if "F02" in pts else tx
            # Original extents of the D3 band
            xL_orig = F0x
            xR_orig = pts["F02"][0] if "F02" in pts else tx
            Lb = abs(pts["Bx"][0] - pts["Fx"][0])
            if Lb > SPLIT_THRESHOLD:
                mid_x = _split_mid_int(pts["Fx"][0], pts["Bx"][0])
                # First segment: from xL_orig to mid_x (clamped)
                x0c = max(x_left_limit, xL_orig)
                x1c = min(mid_x, x_right_limit)
                if x1c > x0c:
                    groups["bottom"]["D3"].append(_rectU(x0c, 0, x1c, F0y))
                # Second segment: from mid_x to xR_orig (clamped)
                x0c = max(x_left_limit, mid_x)
                x1c = min(xR_orig, x_right_limit)
                if x1c > x0c:
                    groups["bottom"]["D3"].append(_rectU(x0c, 0, x1c, F0y))
            else:
                # Single segment case, clamp to limits
                x0c = max(x_left_limit, xL_orig)
                x1c = min(xR_orig, x_right_limit)
                if x1c > x0c:
                    groups["bottom"]["D3"].append(_rectU(x0c, 0, x1c, F0y))
        if draw["D4"]:
            groups["right"]["D4"].append([
                pts["Dx2"],
                pts["D02x"],
                pts["F02"],
                pts["Bx"],
                pts["Dx2"],
            ])
        if draw["D5"]:
            # D5 droite pour v2 : un unique rectangle 0 → By4_use scindé une seule fois.
            # Use the exact banquette split height if available to align the
            # backrest scission.  The seat on the right branch starts at
            # 'profondeur' (depth) and ends at By4_use.y.  When a split height
            # has been recorded in __SPLIT_Y_RIGHT, calculate the mirrored
            # lower bound so that the median of (seat_y0, seat_y1) equals the
            # split.  Otherwise, fall back to the old behaviour.
            x0 = pts["D02x"][0]
            y0, y1 = 0, By4_use[1]
            y_split = pts.get("__SPLIT_Y_RIGHT", None)
            if y_split is not None:
                seat_y1 = y1
                seat_y0 = 2 * y_split - seat_y1
            else:
                # fallback: use the bottom y of the right seat (F02.y if present, else Fy3.y or depth)
                if "F02" in pts:
                    seat_y0 = pts["F02"][1]
                elif "Fy3" in pts:
                    seat_y0 = pts["Fy3"][1]
                else:
                    seat_y0 = profondeur
                seat_y1 = y1
            groups["right"]["D5"] += _build_dossier_vertical_rects(
                x0, tx, y0, y1,
                seat_y0, seat_y1
            )

    elif variant == "v3":
        if draw["D1"]:
            # D1 gauche — scission alignée sur la banquette gauche
            x0, x1 = 0, F0x
            y0, y1 = pts["Fy"][1], By_use[1]
            seat_y0, seat_y1 = pts["Fy"][1], pts["By"][1]
            groups["left"]["D1"] += _build_dossier_vertical_rects(
                x0, x1, y0, y1,
                seat_y0, seat_y1
            )
        if draw["D2"]:
            groups["left"]["D2"].append([
                pts["D0x"],
                pts["D0"],
                pts["Dy"],
                pts["Fy"],
                pts["D0x"],
            ])
        if draw["D3"]:
            xL = F0x; xR = pts["Bx"][0]; y0 = 0; y1 = F0y
            if abs(xR - xL) > SPLIT_THRESHOLD:
                mid_x = _split_mid_int(xL, xR)
                groups["bottom"]["D3"] += [_rectU(xL, y0, mid_x, y1), _rectU(mid_x, y0, xR, y1)]
            else:
                groups["bottom"]["D3"].append(_rectU(xL, y0, xR, y1))
        if draw["D4"]:
            bx0 = pts["Bx"][0]
            groups["right"]["D4"].append([
                pts["Dx"],
                pts["D02x"],
                pts["F02"],
                pts["Bx"],
                (bx0, 0),
                pts["Dx"],
            ])
        if draw["D5"]:
            # D5 droite pour v3 : un unique rectangle 0 → By4_use scindé une seule fois.
            # Use the exact banquette split height if available to align the
            # backrest scission.  The seat on the right branch starts at
            # 'profondeur' (depth) and ends at By4_use.y.  When a split height
            # has been recorded in __SPLIT_Y_RIGHT, calculate the mirrored
            # lower bound so that the median of (seat_y0, seat_y1) equals the
            # split.  Otherwise, fall back to the old behaviour.
            x0 = pts["D02x"][0]
            y0, y1 = 0, By4_use[1]
            y_split = pts.get("__SPLIT_Y_RIGHT", None)
            if y_split is not None:
                seat_y1 = y1
                seat_y0 = 2 * y_split - seat_y1
            else:
                # fallback: use the bottom y of the right seat (F02.y if present, else Fy3.y or depth)
                if "F02" in pts:
                    seat_y0 = pts["F02"][1]
                elif "Fy3" in pts:
                    seat_y0 = pts["Fy3"][1]
                else:
                    seat_y0 = profondeur
                seat_y1 = y1
            groups["right"]["D5"] += _build_dossier_vertical_rects(
                x0, tx, y0, y1,
                seat_y0, seat_y1
            )

    else:  # v4
        if draw["D1"]:
            # D1 gauche — scission alignée sur la banquette gauche, incluant la lame basse
            x0, x1 = 0, F0x
            # inclut la lame basse : zone 0 → By_use.y
            y0, y1 = 0, By_use[1]
            # fallback pour Fy : si absent, utiliser F0y
            seat_y0_left = (pts.get("Fy", [None, None])[1] if "Fy" in pts else F0y)
            # fallback pour By : si absent, utiliser By_use.y
            seat_y1_left = (pts.get("By", [None, None])[1] if "By" in pts else By_use[1])
            groups["left"]["D1"] += _build_dossier_vertical_rects(
                x0, x1, y0, y1,
                seat_y0_left, seat_y1_left
            )
        if draw["D2"]:
            groups["left"]["D2"].append([
                pts["D0x"],
                pts["Dx"],
                pts["Fx"],
                pts["F0"],
                pts["D0x"],
            ])
        if draw["D3"]:
            # ----- Clip and split the bottom backrest D3 for v4 -----
            # 1) Determine left and right limits
            # Left limit: the right edge of D2 (Dx.x) if it exists, otherwise Fx.x or F0.x
            x_left_limit = (
                pts["Dx"][0] if "Dx" in pts else (
                    pts["Fx"][0] if "Fx" in pts else F0x
                )
            )
            # Only consider the right column if D5 is active
            # The right column exists if either the bottom-right backrest (D4) or
            # the top-right backrest (D5) is active. Without this, D3 can extend
            # too far to the right when only D4 is present (dossier_bas=True but
            # dossier_right=False).  Clipping based on D4 as well ensures the
            # bottom backrest is properly limited.
            have_right_col = bool(draw.get("D4") or draw.get("D5"))
            if have_right_col:
                if "F02x" in pts:
                    x_right_limit = pts["F02x"][0]
                elif "D02x" in pts:
                    x_right_limit = pts["D02x"][0]
                else:
                    x_right_limit = tx
            else:
                x_right_limit = tx
            # If no space remains, skip drawing D3
            if x_right_limit > x_left_limit:
                # Split only if the bottom seat actually split.
                x_mid_mark = pts.get("__SPLIT_X_BOTTOM")
                if x_mid_mark is not None:
                    # Clamp x_mid within the effective span
                    x_mid = max(x_left_limit, min(x_mid_mark, x_right_limit))
                    if x_mid > x_left_limit:
                        groups["bottom"]["D3"].append(_rectU(x_left_limit, 0, x_mid, F0y))
                    if x_right_limit > x_mid:
                        groups["bottom"]["D3"].append(_rectU(x_mid, 0, x_right_limit, F0y))
                else:
                    # No seat split: draw a single continuous bottom backrest
                    groups["bottom"]["D3"].append(_rectU(x_left_limit, 0, x_right_limit, F0y))
        F02x = pts["D02x"][0]
        y0 = F0y
        y1 = y0 + profondeur
        # Only draw the right backrest D4 if both D4 and D5 are active (right side requested).
        # In v4 the shape of D4 depends on whether a bottom backrest (D3) exists.  When a
        # méridienne is present, ``By4_use`` records the effective top of the back (reduced
        # height), so we use it instead of ``By4`` to avoid drawing into the méridienne gap.
        if draw.get("D4") and draw.get("D5"):
            # Select the appropriate top point: By4_use takes precedence over the full By4 when a méridienne is active.
            top_pt = By4_use
            if draw.get("D3"):
                # with bottom backrest: D4 = Dy3 - top_pt - D02x - D02 - Dy3
                groups["right"]["D4"].append([
                    pts["Dy3"], top_pt, pts["D02x"], pts["D02"], pts["Dy3"],
                ])
            else:
                # without bottom backrest: D4 = Dy3 - D02y - Bx - top_pt - Dy3
                groups["right"]["D4"].append([
                    pts["Dy3"], pts["D02y"], pts["Bx"], top_pt, pts["Dy3"],
                ])
        if draw["D5"]:
            y_top = By4_use[1]
            # D5 droite — scission alignée sur la banquette droite au-dessus de l'assise
            # fallback pour seat_y0_right : Fy3.y si présent, sinon Fy.y, sinon F0y+profondeur
            seat_y0_right = (
                pts.get("Fy3", [None, None])[1] if "Fy3" in pts else (
                    pts.get("Fy", [None, None])[1] if "Fy" in pts else F0y + profondeur
                )
            )
            # zone au-dessus de l'assise : F0y+profondeur → y_top
            groups["right"]["D5"] += _build_dossier_vertical_rects(
                F02x, tx, F0y + profondeur, y_top,
                seat_y0_right, By4_use[1]
            )
    return groups

def _append_groups_to_polys_U(polys, groups):
    order = {"left":["D1","D2"], "bottom":["D3"], "right":["D4","D5"]}
    # Build a parallel list of sides corresponding to each appended dossier polygon.
    dossiers_sides = []
    for side in ("left","bottom","right"):
        for d in order[side]:
            for poly in groups[side].get(d, []):
                polys["dossiers"].append(poly)
                dossiers_sides.append(side)
    polys["dossiers_by_side"] = groups  # info
    # Store the side for each dossier polygon in order of appearance.  This
    # aids in filtering out dossiers from deactivated sides when printing
    # dimensions and computing counts.
    polys["dossiers_sides"] = dossiers_sides

# === AUTO optimisé pour U (taille + orientation) ===
def _best_orientation_score_U(variant, pts, drawn, size, traversins=None):
    """
    Determine the optimal orientation for placing cushions in a U‑shaped sofa.

    This version considers potential méridienne limits by using the
    ``By_``/``By4_`` keys for the left and right branches when present.

    Parameters
    ----------
    variant : str
        The sofa variant (v1, v2, v3 or v4).
    pts : dict
        Geometry points defining the sofa.
    drawn : dict
        Flags indicating which backs/arms are drawn.
    size : int
        Size of each cushion.
    traversins : set or None
        A set containing 'g' and/or 'd' if traversins (bolsters) are
        present on the left or right; used to reduce available height.

    Returns
    -------
    tuple
        (score tuple, x_start, x_end, y_left_start, y_right_start)
    """
    F0x, F0y = pts["F0"]
    x_end = _u_variant_x_end(variant, pts)

    def cnt_h(x0, x1):
        return int(max(0, x1 - x0) // size)

    def cnt_v(y0, y1):
        return int(max(0, y1 - y0) // size)

    # vertical limits: take méridienne into account if present
    y_end_L = pts.get("By_", pts["By"])[1]
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins:
        if "g" in traversins:
            y_end_L -= TRAVERSIN_THK
        if "d" in traversins:
            y_end_R -= TRAVERSIN_THK

    def score(shiftL, shiftR):
        xs = F0x + (CUSHION_DEPTH if shiftL else 0)
        xe = x_end - (CUSHION_DEPTH if shiftR else 0)
        bas = cnt_h(xs, xe)
        yL0 = F0y + (0 if (not drawn.get("D1", False) or shiftL) else CUSHION_DEPTH)
        has_right = drawn.get("D4", False) or drawn.get("D5", False)
        yR0 = F0y + (0 if (not has_right or shiftR) else CUSHION_DEPTH)
        g = cnt_v(yL0, y_end_L)
        d = cnt_v(yR0, y_end_R)
        waste = (
            (max(0, xe - xs) % size)
            + (max(0, y_end_L - yL0) % size)
            + (max(0, y_end_R - yR0) % size)
        )
        return ((bas + g + d) * size, -waste, size), xs, xe, yL0, yR0

    cands = [
        score(False, False),
        score(True, False),
        score(False, True),
        score(True, True),
    ]
    return max(cands, key=lambda k: k[0])

def _choose_cushion_size_auto_U(variant, pts, drawn, traversins=None):
    best_s, best_tuple = 65, (-1, -1, -65)
    for s in (65, 80, 90):
        (score_tuple, *_rest) = _best_orientation_score_U(variant, pts, drawn, s, traversins=traversins)
        if score_tuple > best_tuple:
            best_tuple, best_s = score_tuple, s
    return best_s

def _draw_cushions_variant_U(t, tr, variant, pts, size, drawn, traversins=None):
    """
    Draw cushions for the U‑shaped sofa, taking a possible méridienne into account.

    This function uses ``_best_orientation_score_U`` to determine the optimal
    placement and then draws cushions on the bottom and both branches. The
    ``By_``/``By4_`` keys and optional traversins reduce the available
    height as needed.
    """
    (score_tuple, xs, xe, yL0, yR0) = _best_orientation_score_U(
        variant, pts, drawn, size, traversins=traversins
    )
    F0x, F0y = pts["F0"]
    x_col = pts["Bx"][0] if variant in ("v1", "v4") else pts["F02"][0]
    y_end_L = pts.get("By_", pts["By"])[1]
    y_end_R = pts.get("By4_", pts["By4"])[1]
    if traversins:
        if "g" in traversins:
            y_end_L -= TRAVERSIN_THK
        if "d" in traversins:
            y_end_R -= TRAVERSIN_THK

    count = 0
    # bottom
    y = F0y
    x = xs
    while x + size <= xe + 1e-6:
        poly = [
            (x, y),
            (x + size, y),
            (x + size, y + CUSHION_DEPTH),
            (x, y + CUSHION_DEPTH),
            (x, y),
        ]
        draw_polygon_cm(
            t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1
        )
        label_poly(t, tr, poly, f"{size}", font=FONT_CUSHION)
        x += size
        count += 1

    # left branch
    x = F0x
    y = yL0
    while y + size <= y_end_L + 1e-6:
        poly = [
            (x, y),
            (x + CUSHION_DEPTH, y),
            (x + CUSHION_DEPTH, y + size),
            (x, y + size),
            (x, y),
        ]
        draw_polygon_cm(
            t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1
        )
        label_poly(t, tr, poly, f"{size}", font=FONT_CUSHION)
        y += size
        count += 1

    # right branch
    x = x_col
    y = yR0
    while y + size <= y_end_R + 1e-6:
        poly = [
            (x - CUSHION_DEPTH, y),
            (x, y),
            (x, y + size),
            (x - CUSHION_DEPTH, y + size),
            (x - CUSHION_DEPTH, y),
        ]
        draw_polygon_cm(
            t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1
        )
        label_poly(t, tr, poly, f"{size}", font=FONT_CUSHION)
        y += size
        count += 1

    return count

def _render_common_U(
    variant,
    tx,
    ty_left,
    tz_right,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    acc_left,
    acc_bas,
    acc_right,
    coussins,
    window_title,
    compute_fn,
    build_fn,
    traversins=None,
    couleurs=None,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Common rendering routine for all U‑shaped sofa variants.

    This function computes the geometry via ``compute_fn`` (passing
    through ``meridienne_side`` and ``meridienne_len``), builds the
    polygons via ``build_fn``, draws the backs, seats, armrests,
    cushions and traversins, and prints a textual report. The window
    title is augmented to display the méridienne configuration.
    """
    # Compute points with méridienne parameters
    pts = compute_fn(
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        meridienne_side,
        meridienne_len,
    )
    # Build polygons and drawing flags
    polys, drawn = build_fn(
        pts,
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
    )
    # Ensure no seat exceeds maximum length
    _assert_banquettes_max_250(polys)

    # --------------------------------------------------------------------
    # Attach additional context to the polygons dictionary for use in
    # diagnostic functions.  We store the variant name and whether a
    # bottom backrest (dossier_bas) is present.  These attributes
    # enable `_print_dossiers_dimensions` and `_compute_dossiers_count`
    # to apply variant‑specific heuristics when determining which
    # backrest polygons need adjustments (e.g., the “bridging” pieces on
    # certain U variants).  The double underscores help avoid
    # collisions with keys used elsewhere in the polygon data
    # structure.
    polys["__variant"] = variant
    polys["__dossier_bas"] = dossier_bas
    # Store left/right backrest presence for U variants.  This enables
    # diagnostic functions to filter out dossiers when a back is absent.
    polys["__dossier_left"] = dossier_left
    polys["__dossier_right"] = dossier_right

    # Parse traversins and resolve colors
    trv = _parse_traversins_spec(traversins, allowed={"g", "d"})
    legend_items = _resolve_and_apply_colors(couleurs)

    # Setup drawing canvas
    ty_canvas = pts["_ty_canvas"]
    screen = turtle.Screen()
    screen.setup(WIN_W, WIN_H)
    screen.title(
        f"{window_title} — {variant} — tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur}"
        f" — méridienne {meridienne_side or '-'}={meridienne_len}"
    )
    t = turtle.Turtle(visible=False)
    t.speed(0)
    screen.tracer(False)
    tr = WorldToScreen(tx, ty_canvas, WIN_W, WIN_H, PAD_PX, ZOOM)

    # Draw backs, seats and armrests
    for p in polys["dossiers"]:
        if _poly_has_area(p):
            draw_polygon_cm(t, tr, p, fill=COLOR_DOSSIER)
    for p in polys["banquettes"]:
        draw_polygon_cm(t, tr, p, fill=COLOR_ASSISE)
    for p in polys["accoudoirs"]:
        draw_polygon_cm(t, tr, p, fill=COLOR_ACC)

    # Draw traversins and count
    n_traversins = _draw_traversins_U_common(
        t, tr, variant, pts, profondeur, trv
    )

    # Dimension arrows
    draw_double_arrow_vertical_cm(
        t, tr, -25, 0, ty_left, f"{ty_left} cm"
    )
    draw_double_arrow_vertical_cm(
        t, tr, tx + 25, 0, tz_right, f"{tz_right} cm"
    )
    draw_double_arrow_horizontal_cm(
        t, tr, -25, 0, tx, f"{tx} cm"
    )

    # Label seats : afficher les dimensions sur deux lignes. Décaler légèrement selon l'orientation et la position.
    banquette_sizes = []
    for poly in polys["banquettes"]:
        L, P = banquette_dims(poly)
        banquette_sizes.append((L, P))
        # Première dimension sans unité suivie d'un « x », seconde avec « cm »
        text = f"{L}x\n{P} cm"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Si la banquette est plus haute que large, décaler horizontalement en fonction de sa position
        if bb_h >= bb_w:
            cx = sum(xs) / len(xs)
            # Séparer par rapport à la moitié de la largeur totale (tx) pour savoir à quel côté se trouve la banquette
            # Réduction d'environ 3 cm par rapport aux offsets précédents :
            # Branche gauche (cx < tx/2) : CUSHION_DEPTH+7 ; branche droite : -(CUSHION_DEPTH-8)
            dx = (CUSHION_DEPTH + 7) if cx < tx / 2.0 else -(CUSHION_DEPTH - 8)
            label_poly_offset_cm(t, tr, poly, text, dx_cm=dx, dy_cm=0.0)
        else:
            # Si la banquette est plus large que haute, centrer simplement
            label_poly(t, tr, poly, text)

    # Label backs and armrests
    # Annotate only the first non-degenerate backrest with its thickness
    # Annoter dossiers et accoudoirs avec leurs épaisseurs
    _label_backrests_armrests(t, tr, polys)

    # Draw cushions
    spec = _parse_coussins_spec(coussins)
    # Préparer des compteurs pour le rapport détaillé : nombre de coussins selon
    # les tailles 65 cm, 80 cm, 90 cm et valise.
    nb_coussins_65 = 0
    nb_coussins_80 = 0
    nb_coussins_90 = 0
    nb_coussins_valise = 0
    if spec["mode"] == "auto":
        # auto : une seule taille choisie parmi (65,80,90) pour minimiser le déchet
        size = _choose_cushion_size_auto_U(
            variant,
            pts,
            drawn,
            traversins=trv,
        )
        cushions_count = _draw_cushions_variant_U(
            t,
            tr,
            variant,
            pts,
            size,
            drawn,
            traversins=trv,
        )
        total_line = f"{coussins} → {cushions_count} × {size} cm"
        # Répartition des coussins par tailles pour le rapport détaillé
        if size == 65:
            nb_coussins_65 = cushions_count
        elif size == 80:
            nb_coussins_80 = cushions_count
        elif size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    elif spec["mode"] == "80-90":
        # mode 80-90 : chaque côté (bas/gauche/droite) peut choisir 80 ou 90 cm indépendamment
        best = _optimize_80_90_U(
            variant,
            pts,
            drawn,
            traversins=trv,
        )
        if not best:
            raise ValueError('Aucune configuration "80-90" valide pour U.')
        sizes = best["sizes"]
        shiftL = best.get("shiftL", False)
        shiftR = best.get("shiftR", False)
        cushions_count = _draw_U_with_sizes(
            variant,
            t,
            tr,
            pts,
            sizes,
            drawn,
            shiftL,
            shiftR,
            traversins=trv,
        )
        sb = sizes["bas"]; sg = sizes["gauche"]; sd = sizes["droite"]
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg, "droite": sd},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # Répartition des coussins par tailles selon le nombre de coussins posés par côté
        counts_dict = best.get("counts", best.get("eval", {}).get("counts"))
        if counts_dict:
            for side, size_val in [("bas", sb), ("gauche", sg), ("droite", sd)]:
                c = counts_dict.get(side, 0)
                if not c:
                    continue
                if size_val == 65:
                    nb_coussins_65 += c
                elif size_val == 80:
                    nb_coussins_80 += c
                elif size_val == 90:
                    nb_coussins_90 += c
                else:
                    nb_coussins_valise += c
    elif spec["mode"] == "fixed":
        size = int(spec["fixed"])
        cushions_count = _draw_cushions_variant_U(
            t,
            tr,
            variant,
            pts,
            size,
            drawn,
            traversins=trv,
        )
        total_line = f"{coussins} → {cushions_count} × {size} cm"
        # Répartition des coussins par tailles pour la taille fixe
        if size == 65:
            nb_coussins_65 = cushions_count
        elif size == 80:
            nb_coussins_80 = cushions_count
        elif size == 90:
            nb_coussins_90 = cushions_count
        else:
            nb_coussins_valise = cushions_count
    else:
        # valise : plage de tailles avec contrainte de delta ≤ 5 cm
        best = _optimize_valise_U(
            variant,
            pts,
            drawn,
            spec["range"],
            spec["same"],
            traversins=trv,
        )
        if not best:
            raise ValueError("Aucune configuration valise valide pour U.")
        sizes = best["sizes"]
        shiftL = best.get("shiftL", False)
        shiftR = best.get("shiftR", False)
        cushions_count = _draw_U_with_sizes(
            variant,
            t,
            tr,
            pts,
            sizes,
            drawn,
            shiftL,
            shiftR,
            traversins=trv,
        )
        sb = sizes["bas"]; sg = sizes["gauche"]; sd = sizes["droite"]
        total_line = _format_valise_counts_console(
            {"bas": sb, "gauche": sg, "droite": sd},
            best.get("counts", best.get("eval", {}).get("counts")),
            cushions_count,
        )
        # En mode valise U, tous les coussins sont considérés comme valises
        nb_coussins_valise = cushions_count

    # Title and legend
    draw_title_center(
        t, tr, tx, ty_canvas, "Canapé en U sans angle"
    )
    draw_legend(
        t, tr, tx, ty_canvas, items=legend_items, pos="top-center"
    )

    # Finalize drawing
    screen.tracer(True)
    t.hideturtle()

    # Calcul du bonus de scission pour les dossiers
    split_flags = polys.get("split_flags", {})
    dossier_bonus = int(
        split_flags.get("left", False) and (drawn.get("D1") or drawn.get("D2"))
    ) + int(
        split_flags.get("bottom", False) and drawn.get("D3")
    ) + int(
        split_flags.get("right", False) and drawn.get("D5")
    )
    # Comptage pondéré des dossiers
    dossiers_count = _compute_dossiers_count(polys)
    # Formater le nombre de dossiers en évitant les décimales inutiles (7.0→"7", 7.5→"7.5")
    nb_dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    nb_banquettes = len(polys["banquettes"])
    nb_banquettes_angle = 0  # Un U sans angle n'a pas de banquettes d'angle
    nb_accoudoirs = len(polys["accoudoirs"])
    # Dimensions des dossiers
    dossier_dims = []
    for dp in polys["dossiers"]:
        try:
            L_d, P_d = banquette_dims(dp)
            dossier_dims.append((L_d, P_d))
        except Exception:
            continue

    # Rapport classique
    print(f"=== Rapport canapé U (variant {variant}) ===")
    print(f"Dimensions : tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur}")
    print(f"Méridienne : {meridienne_side or '-'} ({meridienne_len} cm)")
    print(f"Banquettes : {nb_banquettes} → {banquette_sizes}")
    print(f"Dossiers : {nb_dossiers_str} (+{dossier_bonus} via scission) | Accoudoirs : {nb_accoudoirs}")
    print(f"Banquettes d’angle : {nb_banquettes_angle}")
    print(f"Traversins : {n_traversins} × 70x20")
    print(f"Coussins : {total_line}")

    # Rapport détaillé
    print()
    print("À partir des données console :")
    print(f"Dimensions : tx={tx} / ty(left)={ty_left} / tz(right)={tz_right} — prof={profondeur}")
    print(f"Méridienne : {meridienne_side or '-'} ({meridienne_len} cm)")
    print(f"Nombre de banquettes : {nb_banquettes}")
    print(f"Nombre de banquette d’angle : {nb_banquettes_angle}")
    print(f"Nombre de dossiers : {nb_dossiers_str}")
    print(f"Nombre d’accoudoir : {nb_accoudoirs}")
    # Afficher aussi les dimensions des accoudoirs
    _print_accoudoirs_dimensions(polys)
    # Pour le rapport détaillé, utiliser un format spécifique pour la variante v1
    # et conserver le format générique pour les autres variantes.
    # Les étiquettes des banquettes sont calculées à l'avance car elles
    # servent à l'affichage des mousses et des dossiers.
    _banquette_labels = _compute_banquette_labels(polys)
    if variant == "v1":
        # Imprimer les dossiers selon la formule U v1 (sans angles)
        _print_dossiers_dimensions_U_v1(
            _banquette_labels,
            banquette_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    elif variant == "v2":
        # Imprimer les dossiers selon la formule U v2 (sans angles)
        _print_dossiers_dimensions_U_v2(
            _banquette_labels,
            banquette_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    elif variant == "v3":
        # Imprimer les dossiers selon la nouvelle logique U v3.  Dans cette
        # variante, les dimensions des dossiers ne dépendent pas de la
        # géométrie des polygones mais uniquement des longueurs de mousse
        # (banquettes) et des indicateurs de dossiers (gauche, bas, droite).
        _print_dossiers_dimensions_U_v3(
            _banquette_labels,
            banquette_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    elif variant == "v4":
        # Imprimer les dossiers selon la logique U v4.  Les dimensions des
        # dossiers sont déterminées à partir des longueurs de mousse et des
        # indicateurs de dossier (gauche, bas, droite), conformément aux
        # règles spécifiques de la variante v4.
        _print_dossiers_dimensions_U_v4(
            _banquette_labels,
            banquette_sizes,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    else:
        # Variante générique : réutiliser l’heuristique basée sur les polygones
        _print_dossiers_dimensions(polys)
    # Dimensions des mousses droites (banquettes)
    for label, (L_b, P_b) in zip(_banquette_labels, banquette_sizes):
        print(f"Dimension mousse {label} : {L_b}, {P_b}")
    # Les dimensions des dossiers ne sont plus affichées individuellement pour U.
    # Elles peuvent être calculées via `banquette_dims` mais ne sont pas listées ici.
    # Répartition des coussins par tailles
    print(f"Nombre de coussins 65cm : {nb_coussins_65}")
    print(f"Nombre de coussins 80cm : {nb_coussins_80}")
    print(f"Nombre de coussins 90cm : {nb_coussins_90}")
    print(f"Nombre de coussins valises total : {nb_coussins_valise}")
    print(f"Nombre de traversin : {n_traversins}")
    turtle.done()

def render_U_v1(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    coussins="auto",
    window_title="U v1",
    traversins=None,
    couleurs=None,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Render a U‑shaped sofa variant v1, optionally with a méridienne.

    Validates that the méridienne does not conflict with an armrest on the
    same side or with a missing back, then delegates to the common render
    function. All parameters are forwarded along.
    """
    if meridienne_side == "g":
        if acc_left:
            raise ValueError(
                "Méridienne gauche interdite avec accoudoir gauche."
            )
        if not dossier_left:
            raise ValueError(
                "Méridienne gauche impossible sans dossier gauche."
            )
    if meridienne_side == "d":
        if acc_right:
            raise ValueError(
                "Méridienne droite interdite avec accoudoir droit."
            )
        if not dossier_right:
            raise ValueError(
                "Méridienne droite impossible sans dossier droit."
            )
    _render_common_U(
        "v1",
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        coussins,
        window_title,
        compute_points_U_v1,
        build_polys_U_v1,
        traversins=traversins,
        couleurs=couleurs,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )

def render_U_v2(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    coussins="auto",
    window_title="U v2",
    traversins=None,
    couleurs=None,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Render a U‑shaped sofa variant v2, with optional méridienne.
    Validations ensure the méridienne does not conflict with an armrest
    on the same side and that the relevant back exists.
    """
    if meridienne_side == "g":
        if acc_left:
            raise ValueError(
                "Méridienne gauche interdite avec accoudoir gauche."
            )
        if not dossier_left:
            raise ValueError(
                "Méridienne gauche impossible sans dossier gauche."
            )
    if meridienne_side == "d":
        if acc_right:
            raise ValueError(
                "Méridienne droite interdite avec accoudoir droit."
            )
        if not dossier_right:
            raise ValueError(
                "Méridienne droite impossible sans dossier droit."
            )
    _render_common_U(
        "v2",
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        coussins,
        window_title,
        compute_points_U_v2,
        build_polys_U_v2,
        traversins=traversins,
        couleurs=couleurs,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )

def render_U_v3(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    coussins="auto",
    window_title="U v3",
    traversins=None,
    couleurs=None,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Render a U‑shaped sofa variant v3, with optional méridienne.
    Performs the same validations as other variants before delegating
    to the common render function.
    """
    if meridienne_side == "g":
        if acc_left:
            raise ValueError(
                "Méridienne gauche interdite avec accoudoir gauche."
            )
        if not dossier_left:
            raise ValueError(
                "Méridienne gauche impossible sans dossier gauche."
            )
    if meridienne_side == "d":
        if acc_right:
            raise ValueError(
                "Méridienne droite interdite avec accoudoir droit."
            )
        if not dossier_right:
            raise ValueError(
                "Méridienne droite impossible sans dossier droit."
            )
    _render_common_U(
        "v3",
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        coussins,
        window_title,
        compute_points_U_v3,
        build_polys_U_v3,
        traversins=traversins,
        couleurs=couleurs,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )

def render_U_v4(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    coussins="auto",
    window_title="U v4",
    traversins=None,
    couleurs=None,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Render a U‑shaped sofa variant v4, with optional méridienne.
    Ensures the méridienne is compatible with armrests and backs before
    delegating to the common render routine.
    """
    if meridienne_side == "g":
        if acc_left:
            raise ValueError(
                "Méridienne gauche interdite avec accoudoir gauche."
            )
        if not dossier_left:
            raise ValueError(
                "Méridienne gauche impossible sans dossier gauche."
            )
    if meridienne_side == "d":
        if acc_right:
            raise ValueError(
                "Méridienne droite interdite avec accoudoir droit."
            )
        if not dossier_right:
            raise ValueError(
                "Méridienne droite impossible sans dossier droit."
            )
    _render_common_U(
        "v4",
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        coussins,
        window_title,
        compute_points_U_v4,
        build_polys_U_v4,
        traversins=traversins,
        couleurs=couleurs,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )

# ---------- AUTO sélection U ----------
def _metrics_U(
    variant,
    tx,
    ty_left,
    tz_right,
    profondeur,
    dossier_left,
    dossier_bas,
    dossier_right,
    acc_left,
    acc_bas,
    acc_right,
    meridienne_side=None,
    meridienne_len=0,
):
    """
    Compute metrics used to automatically select the best U‑shaped sofa variant.

    Returns a 4‑tuple:
      (nb_banquettes, scissions, nb_le_200, ok)

    - nb_banquettes : number of seat polygons after internal splits
    - scissions     : number of extra splits beyond the base 3 (left, bottom, right)
    - nb_le_200     : number of seats whose longest dimension ≤ 200 cm
    - ok            : True if no seat exceeds MAX_BANQUETTE (250 cm), False otherwise

    Additional parameters ``meridienne_side`` and ``meridienne_len`` are
    forwarded to the geometry computation to account for a méridienne.
    """
    comp = {
        "v1": compute_points_U_v1,
        "v2": compute_points_U_v2,
        "v3": compute_points_U_v3,
        "v4": compute_points_U_v4,
    }[variant]
    build = {
        "v1": build_polys_U_v1,
        "v2": build_polys_U_v2,
        "v3": build_polys_U_v3,
        "v4": build_polys_U_v4,
    }[variant]

    pts = comp(
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        meridienne_side,
        meridienne_len,
    )
    polys, _ = build(
        pts,
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
    )

    nb_banquettes = len(polys["banquettes"])
    scissions = max(0, nb_banquettes - 3)

    # Check feasibility: no seat > 250 cm
    try:
        _assert_banquettes_max_250(polys)
        ok = True
    except ValueError:
        ok = False

    # Count seats with largest dimension ≤ 200 cm
    nb_le_200 = sum(
        1 for p in polys["banquettes"] if banquette_dims(p)[0] <= 200
    )

    return nb_banquettes, scissions, nb_le_200, ok

def render_U(
    tx,
    ty_left,
    tz_right,
    profondeur=DEPTH_STD,
    dossier_left=True,
    dossier_bas=True,
    dossier_right=True,
    acc_left=True,
    acc_bas=True,
    acc_right=True,
    coussins="auto",
    variant="auto",
    traversins=None,
    couleurs=None,
    window_title="U — auto",
    meridienne_side=None,
    meridienne_len=0,
):
    """
    High‑level entry point to render a U‑shaped sofa. Automatically selects
    an appropriate variant unless one is specified, taking into account
    méridienne parameters. Validations ensure a méridienne does not
    conflict with armrests or absent backs.

    Parameters are the same as for individual render functions, with
    additional ``meridienne_side`` and ``meridienne_len``.
    """
    # Validate méridienne configuration
    if meridienne_side == "g":
        if acc_left:
            raise ValueError(
                "Méridienne gauche interdite avec accoudoir gauche."
            )
        if not dossier_left:
            raise ValueError(
                "Méridienne gauche impossible sans dossier gauche."
            )
    if meridienne_side == "d":
        if acc_right:
            raise ValueError(
                "Méridienne droite interdite avec accoudoir droit."
            )
        if not dossier_right:
            raise ValueError(
                "Méridienne droite impossible sans dossier droit."
            )

    v = (variant or "auto").lower()
    # If a specific variant is requested, delegate directly
    if v in ("v1", "v2", "v3", "v4"):
        return {
            "v1": render_U_v1,
            "v2": render_U_v2,
            "v3": render_U_v3,
            "v4": render_U_v4,
        }[v](
            tx,
            ty_left,
            tz_right,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            acc_left,
            acc_bas,
            acc_right,
            coussins,
            window_title=f"{window_title} [{v}]",
            traversins=traversins,
            couleurs=couleurs,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )

    # Automatic variant selection
    variants = ["v1", "v2", "v3", "v4"]
    metrics = {
        vv: _metrics_U(
            vv,
            tx,
            ty_left,
            tz_right,
            profondeur,
            dossier_left,
            dossier_bas,
            dossier_right,
            acc_left,
            acc_bas,
            acc_right,
            meridienne_side,
            meridienne_len,
        )
        for vv in variants
    }

    # 1) Keep only feasible variants (no seat > 250 cm)
    ok_variants = [vv for vv in variants if metrics[vv][3]]
    if not ok_variants:
        raise ValueError(
            "Aucune variante U faisable (certaines banquettes resteraient > 250 cm). "
            "Ajustez les dimensions ou la profondeur pour respecter 250 cm par banquette."
        )

    # 2) Minimize number of seats
    min_b = min(metrics[vv][0] for vv in ok_variants)
    tied = [vv for vv in ok_variants if metrics[vv][0] == min_b]

    # 3) Among ties, maximize number of seats ≤ 200 cm
    if len(tied) > 1:
        max_le200 = max(metrics[vv][2] for vv in tied)
        tied = [vv for vv in tied if metrics[vv][2] == max_le200]

    # Final tie‑break: stable preference order
    choice = None
    for pref in ["v2", "v1", "v3", "v4"]:
        if pref in tied:
            choice = pref
            break
    if choice is None:
        choice = tied[0]

    # Delegate to the chosen variant
    return render_U(
        tx,
        ty_left,
        tz_right,
        profondeur,
        dossier_left,
        dossier_bas,
        dossier_right,
        acc_left,
        acc_bas,
        acc_right,
        coussins,
        variant=choice,
        traversins=traversins,
        couleurs=couleurs,
        window_title=window_title,
        meridienne_side=meridienne_side,
        meridienne_len=meridienne_len,
    )

# =====================================================================
# ===================  SIMPLE droit (S1)  =============================
# =====================================================================

def compute_points_simple_S1(tx,
                             profondeur=DEPTH_STD,
                             dossier=True,
                             acc_left=True, acc_right=True,
                             meridienne_side=None, meridienne_len=0):
    if meridienne_side == 'g' and acc_left:
        raise ValueError("Méridienne gauche interdite avec accoudoir gauche.")
    if meridienne_side == 'd' and acc_right:
        raise ValueError("Méridienne droite interdite avec accoudoir droit.")

    xL_in = ACCOUDOIR_THICK if acc_left  else 0
    xR_in = tx - (ACCOUDOIR_THICK if acc_right else 0)
    y_base = DOSSIER_THICK if dossier else 0
    # profondeur passée = profondeur d'assise
    prof_tot = profondeur + y_base  # profondeur TOTALE dossier + assise

    pts = {}
    # Axe Y du canapé : de 0 (sol) à prof_tot
    pts["Ay"]  = (0, 0);          pts["Ay2"] = (0, prof_tot)
    pts["Ax"]  = (tx, 0);         pts["Ax2"] = (tx, prof_tot)
    # Banquette et assise : démarre à y_base et monte jusqu'à prof_tot
    pts["B0"]  = (xL_in, y_base); pts["By"]  = (xL_in, prof_tot)
    pts["Bx"]  = (xR_in, y_base); pts["Bx2"] = (xR_in, prof_tot)
    # Pieds avant au sol
    pts["D0"]  = (xL_in, 0);      pts["Dx"]  = (xR_in, 0)

    if meridienne_side == 'g' and meridienne_len > 0:
        start_x = min(max(xL_in + meridienne_len, xL_in), xR_in)
        pts["D0_m"] = (start_x, 0); pts["B0_m"] = (start_x, y_base)
    if meridienne_side == 'd' and meridienne_len > 0:
        end_x = max(min(xR_in - meridienne_len, xR_in), xL_in)
        pts["Dx_m"] = (end_x, 0); pts["Bx_m"] = (end_x, y_base)

    pts["_tx"] = tx
    # on conserve la profondeur d'assise dans _prof
    pts["_prof"] = profondeur
    return pts

def build_polys_simple_S1(pts, dossier=True, acc_left=True, acc_right=True,
                          meridienne_side=None, meridienne_len=0):
    polys = {"banquettes": [], "dossiers": [], "accoudoirs": []}
    # --- Ajout pour scission de dossier si banquette scindée ---
    mid_x = None

    ban = [pts["By"], pts["B0"], pts["Bx"], pts["Bx2"], pts["By"]]
    L = abs(pts["Bx"][0] - pts["B0"][0])
    split = False
    if L > SPLIT_THRESHOLD:
        split = True
        mid_x = _split_mid_int(pts["B0"][0], pts["Bx"][0])
        left  = [pts["By"], pts["B0"], (mid_x, pts["B0"][1]), (mid_x, pts["By"][1]), pts["By"]]
        right = [(mid_x, pts["By"][1]), (mid_x, pts["B0"][1]), pts["Bx"], pts["Bx2"], (mid_x, pts["By"][1])]
        polys["banquettes"] += [left, right]
    else:
        polys["banquettes"].append(ban)

    if dossier:
        x0, x1 = pts["D0"][0], pts["Dx"][0]
        if meridienne_side == 'g' and meridienne_len > 0: x0 = pts["D0_m"][0]
        if meridienne_side == 'd' and meridienne_len > 0: x1 = pts["Dx_m"][0]
        if x1 > x0 + 1e-6:
            # Si banquette scindée et mid_x tombe dans le segment → scinder le dossier aussi
            if (mid_x is not None) and (x0 < mid_x < x1):
                left_dossier  = [(x0,0), (mid_x,0), (mid_x,DOSSIER_THICK), (x0,DOSSIER_THICK), (x0,0)]
                right_dossier = [(mid_x,0), (x1,0), (x1,DOSSIER_THICK), (mid_x,DOSSIER_THICK), (mid_x,0)]
                polys["dossiers"] += [left_dossier, right_dossier]
            else:
                # sinon, un seul dossier
                polys["dossiers"].append([(x0,0),(x1,0),(x1,DOSSIER_THICK),(x0,DOSSIER_THICK),(x0,0)])

    if acc_left:
        if dossier:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By"], pts["D0"], pts["Ay"]])
        else:
            polys["accoudoirs"].append([pts["Ay"], pts["Ay2"], pts["By"], pts["B0"], pts["Ay"]])
    if acc_right:
        if dossier:
            polys["accoudoirs"].append([pts["Bx2"], pts["Dx"], pts["Ax"], pts["Ax2"], pts["Bx2"]])
        else:
            polys["accoudoirs"].append([pts["Bx2"], pts["Ax2"], pts["Ax"], pts["Bx"], pts["Bx2"]])

    polys["split_flags"]={"center":split}
    return polys

def _choose_cushion_size_auto_simple_S1(x0, x1, candidates=(65, 80, 90)):
    """
    Choisit automatiquement une taille de coussin parmi ``candidates`` pour une banquette simple.

    La règle de décision privilégie le moins de déchet et, en cas d'égalité,
    la taille la plus grande.

    Paramètres :
      x0, x1    : coordonnées de début et de fin disponibles pour les coussins
      candidates: iterable d'entiers (tailles possibles), par défaut (65, 80, 90)

    Retourne :
      int : la taille choisie parmi ``candidates``.
    """
    usable = max(0, x1 - x0)
    best = None
    best_score = None
    for s in candidates:
        waste = usable % s if usable > 0 else 0
        score = (waste, -s)
        if best_score is None or score < best_score:
            best_score = score
            best = s
    return best

def _draw_coussins_simple_S1(t, tr, pts, size,
                             meridienne_side=None, meridienne_len=0,
                             traversins=None):
    x0 = pts["B0"][0]; x1 = pts["Bx"][0]
    if meridienne_side == 'g' and meridienne_len > 0:
        x0 = max(x0, pts.get("B0_m", (x0, 0))[0])
    if meridienne_side == 'd' and meridienne_len > 0:
        x1 = min(x1, pts.get("Bx_m", pts["Bx"])[0])
    if traversins:
        if "g" in traversins: x0 += TRAVERSIN_THK
        if "d" in traversins: x1 -= TRAVERSIN_THK

    def count(off):
        xs = x0 + off; xe = x1
        return int(max(0, xe - xs) // size)
    off = CUSHION_DEPTH if count(CUSHION_DEPTH) > count(0) else 0

    y = pts["B0"][1]
    x = x0 + off; n = 0
    while x + size <= x1 + 1e-6:
        poly = [(x, y), (x+size, y), (x+size, y+CUSHION_DEPTH), (x, y+CUSHION_DEPTH), (x, y)]
        draw_polygon_cm(t, tr, poly, fill=COLOR_CUSHION, outline=COLOR_CONTOUR, width=1)
        label_poly(t, tr, poly, f"{size}", font=FONT_CUSHION)
        x += size; n += 1
    return n

def render_Simple1(tx,
                   profondeur=DEPTH_STD,
                   dossier=True,
                   acc_left=True, acc_right=True,
                   meridienne_side=None, meridienne_len=0,
                   coussins="auto",
                   traversins=None,
                   couleurs=None,
                   window_title="Canapé simple 1"):
    pts   = compute_points_simple_S1(tx, profondeur, dossier, acc_left, acc_right,
                                     meridienne_side, meridienne_len)
    polys = build_polys_simple_S1(pts, dossier, acc_left, acc_right,
                                  meridienne_side, meridienne_len)
    _assert_banquettes_max_250(polys)

    trv = _parse_traversins_spec(traversins, allowed={"g","d"})
    legend_items = _resolve_and_apply_colors(couleurs)

    # profondeur totale pour l'affichage : dossier + assise
    y_base = DOSSIER_THICK if dossier else 0
    prof_tot = profondeur + y_base

    screen = turtle.Screen(); screen.setup(WIN_W, WIN_H)
    screen.title(f"{window_title} — tx={tx} / prof={profondeur} — méridienne {meridienne_side or '-'}={meridienne_len} — coussins={coussins}")
    t = turtle.Turtle(visible=False); t.speed(0); screen.tracer(False)
    # utiliser la profondeur totale pour le repère
    tr = WorldToScreen(tx, prof_tot, WIN_W, WIN_H, PAD_PX, ZOOM)

    # (Quadrillage et repères supprimés)

    for p in polys["dossiers"]:
        if _poly_has_area(p):  draw_polygon_cm(t, tr, p, fill=COLOR_DOSSIER)
    for p in polys["banquettes"]:
        draw_polygon_cm(t, tr, p, fill=COLOR_ASSISE)
    for p in polys["accoudoirs"]:
        draw_polygon_cm(t, tr, p, fill=COLOR_ACC)

    # Traversins + comptage (on travaille avec la profondeur totale)
    n_traversins = _draw_traversins_simple_S1(t, tr, pts, prof_tot, dossier, trv)

    # Flèche de profondeur = profondeur TOTALE (dossier + assise)
    # - avec dossier: prof_tot = profondeur + DOSSIER_THICK, ex : 80 cm
    # - sans dossier: prof_tot = profondeur, ex : 70 cm
    draw_double_arrow_vertical_cm(
        t, tr,
        -25,
        0,
        prof_tot,
        f"{prof_tot} cm"
    )
    # Largeur identique
    draw_double_arrow_horizontal_cm(t, tr, -25, 0, tx, f"{tx} cm")

    banquette_sizes = []
    for poly in polys["banquettes"]:
        L, P = banquette_dims(poly)
        banquette_sizes.append((L, P))
        # Première dimension sans unité avec un « x », seconde dimension avec « cm »
        text = f"{L}x\n{P} cm"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bb_w = max(xs) - min(xs)
        bb_h = max(ys) - min(ys)
        # Décaler horizontalement si la banquette est plus haute que large, pour éloigner légèrement le texte des coussins
        # Offset réduit : 3 cm de moins que la version précédente
        if bb_h >= bb_w:
            label_poly_offset_cm(t, tr, poly, text, dx_cm=CUSHION_DEPTH + 7, dy_cm=0.0)
        else:
            label_poly(t, tr, poly, text)
    # Annotate only the first non-degenerate backrest with its thickness
    # Annoter dossiers et accoudoirs avec leurs épaisseurs
    _label_backrests_armrests(t, tr, polys)

    # ===== COUSSINS =====
    spec = _parse_coussins_spec(coussins)
    # Compteurs de coussins pour le rapport détaillé
    nb_coussins_65 = 0
    nb_coussins_80 = 0
    nb_coussins_90 = 0
    nb_coussins_valise = 0
    if spec["mode"] == "auto":
        x0 = pts.get("B0_m", pts["B0"])[0] if meridienne_side == 'g' else pts["B0"][0]
        x1 = pts.get("Bx_m", pts["Bx"])[0] if meridienne_side == 'd' else pts["Bx"][0]
        if trv:
            if "g" in trv: x0 += TRAVERSIN_THK
            if "d" in trv: x1 -= TRAVERSIN_THK
        size = _choose_cushion_size_auto_simple_S1(x0, x1)
        nb_coussins = _draw_coussins_simple_S1(t, tr, pts, size, meridienne_side, meridienne_len, traversins=trv)
        total_line = f"{coussins} → {nb_coussins} × {size} cm"
        # Mise à jour des compteurs pour le mode automatique
        if size == 65:
            nb_coussins_65 = nb_coussins
        elif size == 80:
            nb_coussins_80 = nb_coussins
        elif size == 90:
            nb_coussins_90 = nb_coussins
        else:
            nb_coussins_valise = nb_coussins
    elif spec["mode"] == "fixed":
        size = int(spec["fixed"])
        nb_coussins = _draw_coussins_simple_S1(t, tr, pts, size, meridienne_side, meridienne_len, traversins=trv)
        total_line = f"{coussins} → {nb_coussins} × {size} cm"
        # Mise à jour des compteurs pour le mode fixe
        if size == 65:
            nb_coussins_65 = nb_coussins
        elif size == 80:
            nb_coussins_80 = nb_coussins
        elif size == 90:
            nb_coussins_90 = nb_coussins
        else:
            nb_coussins_valise = nb_coussins
    else:
        best = _optimize_valise_simple(pts, spec["range"], meridienne_side, meridienne_len, traversins=trv)
        if not best:
            raise ValueError("Aucune configuration valise valide pour S1.")
        size = best["size"]
        nb_coussins = _draw_simple_with_size(t, tr, pts, size, meridienne_side, meridienne_len, traversins=trv)
        total_line = f"{nb_coussins} × {size} cm"
        # Mise à jour des compteurs pour le mode valise
        if size == 65:
            nb_coussins_65 = nb_coussins
        elif size == 80:
            nb_coussins_80 = nb_coussins
        elif size == 90:
            nb_coussins_90 = nb_coussins
        else:
            nb_coussins_valise = nb_coussins

    # Légende
    draw_legend(t, tr, tx, profondeur, items=legend_items, pos="top-right")

    screen.tracer(True); t.hideturtle()
    add_split = int(polys.get("split_flags",{}).get("center",False) and dossier)
    print("=== Rapport Canapé simple 1 ===")
    print(f"Dimensions : {tx}×{profondeur} cm")
    print(f"Banquettes : {len(polys['banquettes'])} → {banquette_sizes}")
    # Comptage pondéré des dossiers : <=110cm → 0.5, >110cm → 1
    dossiers_count = _compute_dossiers_count(polys)
    dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    print(f"Dossiers   : {dossiers_str} (+{add_split} via scission)  |  Accoudoirs : {len(polys['accoudoirs'])}")
    print(f"Banquettes d’angle : 0")
    print(f"Traversins : {n_traversins} × 70x20")
    print(f"Coussins   : {total_line}")
    if meridienne_side:
        print(f"Méridienne : côté {'gauche' if meridienne_side=='g' else 'droit'} — {meridienne_len} cm")
    # Bloc détaillé basé sur les données du schéma
    nb_banquettes = len(polys["banquettes"])
    nb_banquettes_angle = 0  # Canapé simple : pas de banquettes d’angle
    nb_accoudoirs = len(polys["accoudoirs"])
    # Formater le nombre de dossiers en évitant les décimales inutiles
    nb_dossiers_str = f"{int(dossiers_count)}" if abs(dossiers_count - int(dossiers_count)) < 1e-9 else f"{dossiers_count}"
    print()
    print("À partir des données console :")
    print(f"Dimensions : {tx}×{profondeur} cm")
    print(f"Nombre de banquettes : {nb_banquettes}")
    print(f"Nombre de banquette d’angle : {nb_banquettes_angle}")
    print(f"Nombre de dossiers : {nb_dossiers_str}")
    print(f"Nombre d’accoudoir : {nb_accoudoirs}")
    # Afficher aussi les dimensions des accoudoirs
    _print_accoudoirs_dimensions(polys)
    _print_dossiers_dimensions(polys)
    # Dimensions des dossiers pour canapé simple : appliquer les
    # corrections liées à la méridienne selon les règles spécifiées.
    _banquette_labels = _compute_banquette_labels(polys)
    if dossier:  # n'imprimer les dossiers que s'ils existent
        # Le canapé simple n'a qu'un seul côté de dossier ; on utilise
        # le préfixe sans mentionner de côté explicite.
        print("Dossiers :")
        _print_dossiers_dimensions_simple_S1(
            _banquette_labels,
            banquette_sizes,
            meridienne_side=meridienne_side,
            meridienne_len=meridienne_len,
        )
    for label, (L_b, P_b) in zip(_banquette_labels, banquette_sizes):
        print(f"Dimension mousse {label} : {L_b}, {P_b}")
    print(f"Nombre de coussins 65cm : {nb_coussins_65}")
    print(f"Nombre de coussins 80cm : {nb_coussins_80}")
    print(f"Nombre de coussins 90cm : {nb_coussins_90}")
    print(f"Nombre de coussins valises total : {nb_coussins_valise}")
    print(f"Nombre de traversin : {n_traversins}")
    turtle.done()

# =====================================================================
# =====================  TESTS ÉTENDUS (30)  ==========================
# =====================================================================




def TEST_22_LNF_v1_mer_bas_split_TRb_gs():
    render_LNF(
        tx=500, ty=500, profondeur=70,
        dossier_left=True, dossier_bas=False,
        acc_left=False, acc_bas=False,
        meridienne_side='', meridienne_len=0,
        coussins="p", variant="v2",
        traversins="None",
        window_title="T22 — LNF v1 | méridienne bas | split bas | g:s | TR bas"
    )


def TEST_23_LNF_v1_grand_scission_valise_TRgb_palette():
    render_LNF(
        tx=540, ty=360, profondeur=70,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="valise", variant="v1",
        traversins="g,b",
        couleurs="accoudoirs:gris foncé; assise:gris très clair presque blanc; coussins:#8B7E74",
        window_title="T23 — LNF v1 | grandes longueurs | valise | TR G+B | palette"
    )


def TEST_24_LNF_v2_mer_gauche_split_TRg_ps():
    render_LNF(
        tx=280, ty=360, profondeur=70,
        dossier_left=True, dossier_bas=True,
        acc_left=False, acc_bas=True,               # méridienne gauche -> pas d'accoudoir gauche (déjà OFF)
        meridienne_side='g', meridienne_len=90,
        coussins="p:s", variant="v2",
        traversins="g",
        window_title="T24 — LNF v2 | méridienne G 90 | split gauche | p:s | TR G"
    )


def TEST_25_LNF_v2_mer_bas_split_TRb_auto():
    render_LNF(
        tx=420, ty=280, profondeur=80,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=False,               # méridienne bas -> pas d'accoudoir bas
        meridienne_side='b', meridienne_len=140,
        coussins="auto", variant="v2",
        traversins="b",
        window_title="T25 — LNF v2 | méridienne bas 140 | split bas | auto | TR bas"
    )


def TEST_26_LF_mer_bas_TRgb_palette_dict():
    render_LF_variant(
        tx=420, ty=440, profondeur=80,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=False,               # méridienne bas -> pas d'accoudoir bas
        meridienne_side='b', meridienne_len=50,
        coussins="90", traversins="",
        couleurs={"accoudoirs": "anthracite", "assise": "crème", "coussins": "#c0ffee"},
        window_title="T26 — LF | méridienne bas 100 | TR G+B | palette dict"
    )


def TEST_27_LF_valise_sans_mer_TRg_split():
    render_LF_variant(
        tx=500, ty=500, profondeur=70,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="valise", traversins="g",
        window_title="T27 — LF | valise | sans méridienne | TR G | grandes longueurs"
    )


def TEST_28_S1_TR_both_auto_palette():
    render_Simple1(
        tx=260, profondeur=70, dossier=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="auto", traversins="g,d",
        couleurs="accoudoirs:#444444; assise:#f0f0f0; coussins:#b38b6d",
        window_title="T28 — S1 | dossier | TR G+D | auto | palette"
    )


def TEST_29_S1_mer_droite_120_no_accR_90_TRg():
    render_Simple1(
        tx=401, profondeur=70, dossier=True,
        acc_left=False, acc_right=False,             # méridienne droite -> pas d'accoudoir droit
        meridienne_side='g', meridienne_len=20,
        coussins="90", traversins="g",
        couleurs=None,
        window_title="T29 — S1 | méridienne D 120 | accR OFF | 90 | TR G"
    )


def TEST_30_U_v1_left_TRg_auto_no_dossier_droit():
    render_U(
        tx=440, ty_left=260, tz_right=260, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=False, acc_bas=True, acc_right=False,
        coussins="p", variant="v3", traversins=None,
        meridienne_side='d', meridienne_len=20,
        window_title="T30 — U v1 | pas de dossier droit | TR G | auto"
    )


def TEST_31_U_v1_TR_both_80_palette():
    render_U(
        tx=320, ty_left=200, tz_right=370, profondeur=70,
        # Align parameters with v88 to restore correct dossier count
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=False, acc_bas=True, acc_right=False,
        # Use variant v4 as in v88
        coussins="auto", variant="v4", traversins="d",
        meridienne_side='d', meridienne_len=20,
        couleurs="accoudoirs:#333333; assise:#f5f5f5; coussins:#a67c52",
        window_title="T31 — U v1 | TR G+D | 80 | palette"
    )


def TEST_32_U_auto_valise_g():
    render_U(
        tx=520, ty_left=420, tz_right=420, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=True, acc_right=True,
        coussins="valise", variant="auto", traversins="g",
        couleurs=None,
        window_title="T32 — U auto | valise g"
    )


def TEST_33_U_v3_valise_p_sans_TR():
    render_U(
        tx=460, ty_left=380, tz_right=360, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=True, acc_right=True,
        coussins="p", variant="v3", traversins=None,
        couleurs=None,
        window_title="T33 — U v3 | valise p | sans TR"
    )


def TEST_34_U_v4_TR_both_75_palette_hex():
    render_U(
        tx=300, ty_left=400, tz_right=480, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=True, acc_right=True,
        coussins="75", variant="v4", traversins="g,d",
        couleurs="accoudoirs:#4b4b4b; assise:#f6f6f6; coussins:#8B7E74",
        window_title="T34 — U v4 | TR G+D | 75 | palette hex"
    )


def TEST_35_U2F_mer_g_120_no_accL_s_TRd():
    render_U2f_variant(
        # Restore original dimensions and depth from v88
        tx=417, ty_left=308, tz_right=355, profondeur=70,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=False, acc_right=True,   # méridienne gauche -> pas d'accoudoir gauche
        meridienne_side='', meridienne_len=0,
        # Restore cushions and traversins settings from v88
        coussins="valise", traversins="d",
        window_title="T35 — U2F | méridienne G 120 | accL OFF | s | TR D"
    )


def TEST_36_U2F_mer_d_100_no_accR_80_TRg():
    render_U2f_variant(
        tx=520, ty_left=420, tz_right=330, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=True, acc_right=False,   # méridienne droite -> pas d'accoudoir droit
        meridienne_side='d', meridienne_len=100,
        coussins="g", traversins="g",
        window_title="T36 — U2F | méridienne D 100 | accR OFF | 80 | TR G"
    )


def TEST_37_U2F_valise_same_TR_both():
    render_U2f_variant(
        tx=560, ty_left=540, tz_right=520, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=False, acc_bas=True, acc_right=True,
        meridienne_side='g', meridienne_len=50,
        coussins="g:s", traversins="g,d",
        window_title="T37 — U2F | valise g:s | TR G+D"
    )


def TEST_38_U1F_v1_mer_g_90_no_accL_p_TRd():
    render_U1F(
        tx=400, ty_left=280, tz_right=300, profondeur=70,
        dossier_left=False, dossier_bas=False, dossier_right=True,
        acc_left=False, acc_right=True,                  # méridienne gauche -> pas d'accoudoir gauche
        meridienne_side='g', meridienne_len=90,
        coussins="p", variant="v2",
        traversins="d",
        window_title="T38 — U1F v1 | méridienne G 90 | accL OFF | p | TR D"
    )


def TEST_39_U1F_v2_mer_d_110_no_accR_65_TRg():
    render_U1F(
        tx=500, ty_left=500, tz_right=500, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,                 # méridienne droite -> pas d'accoudoir droit
        meridienne_side='', meridienne_len=0,
        coussins="65", variant="v1",
        traversins="g",
        window_title="T39 — U1F v2 | méridienne D 110 | accR OFF | 65 | TR G"
    )


def TEST_40_U1F_v3_TR_both_valise_g_palette():
    render_U1F(
        tx=380, ty_left=317, tz_right=300, profondeur=70,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="80-90", variant="v3",
        traversins="g",
        couleurs={"accoudoirs": "gris", "assise": "crème", "coussins": "taupe"},
        window_title="T40 — U1F v3 | TR G+D | valise g | palette dict"
    )


def TEST_41_U1F_v4_valise_TRg():
    render_U1F(
        tx=400, ty_left=280, tz_right=320, profondeur=70,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="valise", variant="v4",
        traversins="g",
        window_title="T41 — U1F v4 | valise | TR G"
    )


def TEST_42_U1F_v4_auto_sans_TR():
    render_U1F(
        tx=460, ty_left=400, tz_right=480, profondeur=70,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="auto", variant="v4",
        traversins=None,
        window_title="T42 — U1F v4 | auto | pas de TR"
    )


def TEST_43_U1F_v2_grand_split_TRg_palette():
    render_U1F(
        tx=520, ty_left=450, tz_right=430, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="p:s", variant="v2",
        traversins="g",
        couleurs="accoudoirs:anthracite; assise:gris très clair; coussins:#e0d9c7",
        window_title="T43 — U1F v2 | grandes longueurs (scissions) | p:s | TR G | palette"
    )


def TEST_44_U1F_v3_split_droite_TRd_ps():
    render_U1F(
        tx=460, ty_left=300, tz_right=360, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="p:s", variant="v3",
        traversins="d",
        window_title="T44 — U1F v3 | split droite | p:s | TR D"
    )


def TEST_45_U1F_v4_TR_both_90_palette_dict():
    render_U1F(
        tx=420, ty_left=300, tz_right=300, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="90", variant="v4",
        traversins="g,d",
        couleurs={"accoudoirs": "gris", "assise": "blanc", "coussins": "#8B7E74"},
        window_title="T45 — U1F v4 | TR G+D | 90 | palette dict"
    )


def TEST_46_LNF_v1_palette_lighten_dossiers_auto():
    render_LNF(
        tx=300, ty=280, profondeur=70,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="80", variant="v1",
        traversins=None,
        couleurs={"accoudoirs": "anthracite fonce", "assise": "gris très clair", "coussins": "#b5651d"},
        window_title="T46 — LNF v1 | palette lighten dossiers auto"
    )


def TEST_47_LNF_v2_palette_string_accents_TRb():
    render_LNF(
        tx=320, ty=300, profondeur=80,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="auto", variant="v2",
        traversins="b",
        couleurs="accoudoirs:gris; dossiers:gris clair; assise:crème; coussins:taupe",
        window_title="T47 — LNF v2 | palette string (accents) | TR bas"
    )


def TEST_48_S1_sans_dossier_TR_both_auto():
    render_Simple1(
        tx=300, profondeur=70, dossier=False,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="auto", traversins="g,d",
        couleurs=None,
        window_title="T48 — S1 | sans dossier | TR G+D | auto"
    )


def TEST_49_LF_valise_same_TRg():
    render_LF_variant(
        tx=460, ty=460, profondeur=70,
        dossier_left=True, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="valise", traversins="g",
        couleurs=None,
        window_title="T49 — LF | valise | TR G | mêmes longueurs"
    )


def TEST_50_U_v2_valise_same_TRg_palette():
    render_U(
        tx=460, ty_left=460, tz_right=460, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=True, acc_right=True,
        coussins="valise", variant="v2", traversins="g",
        couleurs="accoudoirs:#444444; assise:#f0f0f0; coussins:#b38b6d",
        window_title="T50 — U v2 | valise | TR G | mêmes longueurs | palette"
    )


def TEST_51_LNF_auto_dossier_bas_seul_TRb():
    # LNF : uniquement dossier bas, choix de variante automatique
    render_LNF(
        tx=280, ty=220, profondeur=70,
        dossier_left=False, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="auto", variant="auto",
        traversins="b",
        couleurs="accoudoirs:gris; assise:gris très clair; coussins:taupe",
        window_title="T51 — LNF auto | dossier bas seul | TR bas"
    )


def TEST_52_LNF_auto_dossier_gauche_seul_TRg_palette_dict():
    # LNF : uniquement dossier gauche, test de variant=auto + palette dictionnaire
    render_LNF(
        tx=240, ty=360, profondeur=70,
        dossier_left=False, dossier_bas=True,
        acc_left=True, acc_bas=True,
        meridienne_side=None, meridienne_len=0,
        coussins="65", variant="auto",
        traversins=None,
        couleurs={"accoudoirs": "anthracite",
                  "assise": "gris très clair",
                  "coussins": "#c8ad7f"},
        window_title="T52 — LNF auto | dossier gauche seul | TR G | palette dict"
    )


def TEST_53_U1F_auto_TR_both_auto_palette():
    # U1F : 3 dossiers, TR gauche + droite, choix auto de la variante
    render_U1F(
        tx=520, ty_left=360, tz_right=380, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="auto", variant="auto",
        traversins="g,d",
        couleurs="accoudoirs:gris foncé; assise:gris très clair; coussins:taupe",
        window_title="T53 — U1F auto | TR G+D | palette"
    )


def TEST_54_U1F_v3_dossiers_gauche_et_bas_TRg():
    # U1F : variante v3 forcée, dossiers gauche + bas uniquement
    render_U1F(
        tx=420, ty_left=320, tz_right=280, profondeur=75,
        dossier_left=True, dossier_bas=True, dossier_right=False,
        acc_left=True, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="p", variant="v3",
        traversins="g",
        window_title="T54 — U1F v3 | dossiers G+bas | TR G"
    )


def TEST_55_U1F_v4_dossier_droit_seul_TRd_palette():
    # U1F : variante v4 forcée, uniquement dossier droit (cas limite pour D5 / couture Dx2–Bx)
    render_U1F(
        tx=450, ty_left=280, tz_right=340, profondeur=70,
        dossier_left=False, dossier_bas=False, dossier_right=True,
        acc_left=False, acc_right=True,
        meridienne_side=None, meridienne_len=0,
        coussins="s", variant="v4",
        traversins="d",
        couleurs="accoudoirs:gris; assise:blanc cassé; coussins:#b5651d",
        window_title="T55 — U1F v4 | dossier droit seul | TR D | palette"
    )

def TEST_56_U_v1_mer_g_120_no_accL_TRg():
    """
    U v1 avec méridienne gauche 120 cm :
    - dossier gauche et bas présents
    - pas d'accoudoir gauche (acc_left=False obligatoire)
    - méridienne sur branche gauche (meridienne_side='g')
    - traversin à gauche
    """
    render_U(
        tx=520, ty_left=450, tz_right=420, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=False, acc_bas=True, acc_right=True,
        meridienne_side="g", meridienne_len=120,
        coussins="auto", variant="v1",
        traversins="g",
        couleurs="accoudoirs:anthracite; assise:gris très clair; coussins:taupe",
        window_title="T56 — U v1 | méridienne G 120 | accL OFF | TR G"
    )


def TEST_57_U_v2_mer_d_100_no_accR_TRd():
    """
    U v2 avec méridienne droite 100 cm :
    - dossier droit et bas présents
    - pas d'accoudoir droit (acc_right=False obligatoire)
    - méridienne sur branche droite (meridienne_side='d')
    - traversin à droite
    """
    render_U(
        tx=580, ty_left=430, tz_right=460, profondeur=80,
        dossier_left=True, dossier_bas=True, dossier_right=True,
        acc_left=True, acc_bas=True, acc_right=False,
        meridienne_side="d", meridienne_len=100,
        coussins="80", variant="v2",
        traversins="d",
        couleurs="accoudoirs:#444444; assise:#f0f0f0; coussins:#b38b6d",
        window_title="T57 — U v2 | méridienne D 100 | accR OFF | TR D"
    )

if __name__ == "__main__":
    #TEST_21_LNF_v1_mer_gauche_split_TRg_p()
    #TEST_22_LNF_v1_mer_bas_split_TRb_gs()
    #TEST_23_LNF_v1_grand_scission_valise_TRgb_palette()
    #TEST_24_LNF_v2_mer_gauche_split_TRg_ps()
    #TEST_25_LNF_v2_mer_bas_split_TRb_auto()
    #TEST_26_LF_mer_bas_TRgb_palette_dict()
    #TEST_27_LF_valise_sans_mer_TRg_split()
    #TEST_28_S1_TR_both_auto_palette()
    #TEST_29_S1_mer_droite_120_no_accR_90_TRg()
    #TEST_30_U_v1_left_TRg_auto_no_dossier_droit()
    #TEST_31_U_v1_TR_both_80_palette()
    #TEST_32_U_auto_valise_g()
    #TEST_33_U_v3_valise_p_sans_TR()
    #TEST_34_U_v4_TR_both_75_palette_hex()
    #TEST_35_U2F_mer_g_120_no_accL_s_TRd()
    #TEST_36_U2F_mer_d_100_no_accR_80_TRg()
    #TEST_37_U2F_valise_same_TR_both()
    #TEST_38_U1F_v1_mer_g_90_no_accL_p_TRd()
    TEST_39_U1F_v2_mer_d_110_no_accR_65_TRg()
    #TEST_40_U1F_v3_TR_both_valise_g_palette()
    #TEST_41_U1F_v4_valise_TRg()
    #TEST_42_U1F_v4_auto_sans_TR()
    #TEST_43_U1F_v2_grand_split_TRg_palette()
    #TEST_44_U1F_v3_split_droite_TRd_ps()
    #TEST_45_U1F_v4_TR_both_90_palette_dict()
    #TEST_46_LNF_v1_palette_lighten_dossiers_auto()
    #TEST_47_LNF_v2_palette_string_accents_TRb()
    #TEST_48_S1_sans_dossier_TR_both_auto()
    #TEST_49_LF_valise_same_TRg()
    #TEST_50_U_v2_valise_same_TRg_palette()
    #TEST_51_LNF_auto_dossier_bas_seul_TRb()
    #TEST_52_LNF_auto_dossier_gauche_seul_TRg_palette_dict()
    #TEST_53_U1F_auto_TR_both_auto_palette()
    #TEST_54_U1F_v3_dossiers_gauche_et_bas_TRg()
    #TEST_55_U1F_v4_dossier_droit_seul_TRd_palette()
    #TEST_56_U_v1_mer_g_120_no_accL_TRg()
    #TEST_57_U_v2_mer_d_100_no_accR_TRd()
    pass

