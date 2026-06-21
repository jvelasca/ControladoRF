"""Límites compartidos de bloques IQ (captura HackRF / demodulación)."""

# Bloque IQ por iteración del hilo de demod (~8 ms @ 2 Msps).
IQ_DEMOD_CHUNK_SAMPLES = 32_768

# Máximo IQ por bloque de demodulación (~131 ms @ 2 Msps).
IQ_DEMOD_MAX_SAMPLES = 262_144

# Ring buffer IQ (~1 s @ 2 Msps).
IQ_RING_MAX_SAMPLES = 1_048_576
