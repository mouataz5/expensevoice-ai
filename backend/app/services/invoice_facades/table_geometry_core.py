"""
Reconstruction géométrique de tableaux : lignes par Y, colonnes par bornes X dérivées de l'en-tête.

Ne pas se fier à l'ordre texte : les coupures entre colonnes sont les milieux entre
les intervalles [x0,x1] des cellules d'en-tête.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass
class TableWordBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return max(0.1, self.y1 - self.y0)


def y_cluster_tolerance_for_words(words: list[TableWordBox]) -> float:
    hs = [w.h for w in words]
    if not hs:
        return 10.0
    med_h = float(median(hs))
    return max(10.0, min(16.0, med_h * 0.42))


def reconstruct_rows_from_boxes(words: list[TableWordBox], y_tol: float) -> list[list[TableWordBox]]:
    """Groupe les mots en lignes par proximité de Y (même bande horizontale)."""
    sy = sorted(words, key=lambda w: (w.yc, w.xc))
    rows: list[list[TableWordBox]] = []
    for w in sy:
        if not rows:
            rows.append([w])
            continue
        mean_y = sum(x.yc for x in rows[-1]) / len(rows[-1])
        if abs(w.yc - mean_y) <= y_tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def column_intervals_from_header_cells(header_cells: list[list[TableWordBox]]) -> list[tuple[float, float]]:
    """Intervalle X couvert par chaque cellule d'en-tête, trié gauche → droite."""
    intervals: list[tuple[float, float]] = []
    for cell in header_cells:
        if not cell:
            continue
        x0 = min(w.x0 for w in cell)
        x1 = max(w.x1 for w in cell)
        intervals.append((float(x0), float(x1)))
    intervals.sort(key=lambda t: t[0])
    return intervals


def detect_column_boundaries_from_header(header_cells: list[list[TableWordBox]]) -> list[float]:
    """
    Seuils X entre colonnes : milieu entre bord droit col i et bord gauche col i+1.
    `cuts[k]` = frontière entre colonne k et k+1 ; mot avec xc <= cuts[k] appartient aux cols 0..k selon assign.
    """
    iv = column_intervals_from_header_cells(header_cells)
    if len(iv) < 2:
        return []
    cuts: list[float] = []
    for i in range(len(iv) - 1):
        cuts.append((iv[i][1] + iv[i + 1][0]) / 2.0)
    return cuts


def assign_cells_to_columns(
    row_words: list[TableWordBox],
    cuts: list[float],
    n_columns: int,
) -> list[list[TableWordBox]]:
    """
    Affecte chaque mot à une colonne par comparaison de xc aux `cuts` (non pas au centre seulement).
    Colonne j : cuts[j-1] < xc <= cuts[j] (cuts[-1] et cuts[0] virtuels ±inf gérés par indices).

    Pour les tableaux facture, préférer `assign_cells_to_column_intervals` avec
    `column_intervals_from_header_cells(en-tête)` : même logique de coupures, mais assignation
    par chevauchement des boîtes X (moins de décalage colonne).
    """
    cols: list[list[TableWordBox]] = [[] for _ in range(n_columns)]
    for w in sorted(row_words, key=lambda w: w.xc):
        j = 0
        while j < len(cuts) and w.xc > cuts[j]:
            j += 1
        if j >= n_columns:
            j = n_columns - 1
        cols[j].append(w)
    return cols


def assign_cells_to_column_intervals(
    row_words: list[TableWordBox],
    column_intervals: list[tuple[float, float]],
) -> list[list[TableWordBox]]:
    """
    Affecte chaque mot à la colonne avec le plus grand chevauchement horizontal [x0,x1] ∩ [a,b].
    Réduit les erreurs vs. binning par seul xc lorsque le token est large ou chevauche une coupure.
    Égalité : premier meilleur (ordre gauche → droite), puis distance |xc - centre| minimale.
    """
    if not column_intervals:
        return []
    n = len(column_intervals)
    centers = [(float(a) + float(b)) / 2.0 for a, b in column_intervals]
    cols: list[list[TableWordBox]] = [[] for _ in range(n)]
    for w in sorted(row_words, key=lambda w: (w.x0, w.xc)):
        best_j = 0
        best_ov = -1.0
        best_d = 1e18
        for j, (a, b) in enumerate(column_intervals):
            fa, fb = float(a), float(b)
            ov = max(0.0, min(w.x1, fb) - max(w.x0, fa))
            d = abs(w.xc - centers[j])
            if ov > best_ov + 1e-6 or (
                abs(ov - best_ov) <= 1e-6 and d < best_d - 1e-6
            ):
                best_ov = ov
                best_j = j
                best_d = d
        if best_ov <= 1e-9:
            best_j = min(range(n), key=lambda j: abs(w.xc - centers[j]))
        cols[best_j].append(w)
    return cols


__all__ = [
    "TableWordBox",
    "y_cluster_tolerance_for_words",
    "reconstruct_rows_from_boxes",
    "column_intervals_from_header_cells",
    "detect_column_boundaries_from_header",
    "assign_cells_to_columns",
    "assign_cells_to_column_intervals",
]
