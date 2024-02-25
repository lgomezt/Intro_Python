import copy
import matplotlib.pyplot as plt
import numpy as np

class MovimientoInvalidoError(Exception):
    pass

def movimiento(posiciones_iniciales, movimiento):
    poste_inicial = movimiento[0]
    poste_final = movimiento[1]
    disco = movimiento[2]
    
    postes = posiciones_iniciales.keys()
    discos_superiores = [i[-1] if len(i) > 0 else 0 for i in posiciones_iniciales.values()]
    discos_superiores = dict(zip(postes, discos_superiores))

    disco_superior_inicial = discos_superiores[poste_inicial]
    disco_superior_final = discos_superiores[poste_final]

    if disco == disco_superior_inicial:
        if (disco_superior_final > disco_superior_inicial) or (disco_superior_final == 0):
            # Hacer una copia profunda para evitar modificar el original
            posiciones_finales = copy.deepcopy(posiciones_iniciales)
            posiciones_finales[poste_inicial].remove(disco)
            posiciones_finales[poste_final].append(disco)
            return posiciones_finales
        else:
            raise MovimientoInvalidoError(f"Movimiento invalido. El disco {disco} es más grande que el disco {disco_superior_final} que está en la cima del poste {poste_final}.")
    else:
        raise MovimientoInvalidoError(f"Movimiento invalido. El disco {disco} no está en la cima del poste {poste_inicial}.")

def dibujar_torres(posiciones, titulo = 'Torre de Hanoi'):
    altura = np.max([np.max(i) if len(i) > 0 else 0 for i in posiciones.values()]) - 1
    fig, ax = plt.subplots(figsize = (8, altura))
    ax.set_title(titulo)
    
    # Definir los postes y el espacio entre ellos
    postes = list(posiciones.keys())
    espacio_postes = np.linspace(1, len(postes)*2, len(postes))
    
    # Altura y anchura de los discos
    altura_disco = 0.4
    max_disco_width = 1.5
    
    for i, poste in enumerate(postes):
        discos = posiciones[poste]
        # Etiqueta del poste
        ax.text(espacio_postes[i], -0.5, f'Poste {poste}', ha='center')
        for j, disco in enumerate(discos):
            # Calcular el ancho del disco basado en su valor
            disco_width = max_disco_width * (disco / max(max(discos), 1)) if discos else 0.1
            bar = ax.bar(espacio_postes[i], altura_disco, width=disco_width, bottom=j*altura_disco, color='skyblue', edgecolor='black')
            # Etiqueta del disco
            ax.text(espacio_postes[i], j*altura_disco + altura_disco/2, f'Disco {disco}', ha='center', va='center')
        
        # Dibujar el poste
        ax.plot([espacio_postes[i], espacio_postes[i]], [0, len(discos)*altura_disco], color='saddlebrown', linewidth=2)

    ax.set_ylim(0, altura)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_frame_on(False)