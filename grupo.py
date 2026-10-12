#!/usr/bin/env python3
"""
O grupo matemático da Urna do Garoto;  —  o chão onde toda a criptografia pisa.
por Garoto do Programa;  (github.com/garotodoprograma404/urna-do-garoto)

Três números e pronto:
  p  primo de 3072 bits
  q  primo de 256 bits que divide p - 1
  g  gerador do subgrupo de ordem q (g^q = 1 mod p, e g ≠ 1)

Segurança: ~128 bits (é o que a NIST recomenda pra depois de 2030 com chave de 3072 bits).
Ler um voto sem a chave exige resolver Diffie-Hellman nesse grupo; o melhor ataque conhecido é o
logaritmo discreto, ~2^128 de trabalho (pelo p de 3072 bits ou pelo q de 256). O mundo tenta desde 1976.

E o detalhe que importa: NENHUM desses números foi escolhido por mim. Eles saem de um hash
de uma frase pública (a SEMENTE). Se eu tivesse escolhido "na mão", você podia desconfiar
de um número com alçapão. Assim não: qualquer um refaz a conta e chega nos mesmos números.

    python3 grupo.py        # refaz o grupo do zero a partir da semente e confere (~20-30 s)
"""

from __future__ import annotations

import hashlib
import math
import secrets
import sys
from dataclasses import dataclass

SEMENTE = "Garoto do Programa; Urna do Garoto; grupo v1"
BITS_P = 3072
BITS_Q = 256


def _primos_pequenos(limite: int) -> list[int]:
    crivo = bytearray([1]) * limite
    crivo[0:2] = b"\x00\x00"
    for i in range(2, math.isqrt(limite) + 1):
        if crivo[i]:
            crivo[i * i :: i] = bytearray(len(crivo[i * i :: i]))
    return [i for i, eh in enumerate(crivo) if eh]


_PEQUENOS = _primos_pequenos(5000)
_PRIMORIAL = math.prod(_PEQUENOS)


def eh_primo(n: int, rodadas: int = 64) -> bool:
    """Miller-Rabin com bases aleatórias. Chance de um composto passar: menor que 4^-64."""
    if n < 2:
        return False
    for pequeno in _PEQUENOS:
        if n % pequeno == 0:
            return n == pequeno
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for _ in range(rodadas):
        x = pow(secrets.randbelow(n - 3) + 2, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _expande(semente: str, rotulo: str, contador: int, bits: int) -> int:
    """Número de `bits` bits tirado da semente com SHAKE-256. Determinístico: ninguém escolhe."""
    dados = f"{semente}|{rotulo}|{contador}".encode()
    return int.from_bytes(hashlib.shake_256(dados).digest(bits // 8), "big")


@dataclass(frozen=True)
class Grupo:
    p: int
    q: int
    g: int

    def pertence(self, x: object) -> bool:
        """x está no subgrupo de ordem q? Toda entrada de fora passa por aqui antes de qualquer conta."""
        return isinstance(x, int) and not isinstance(x, bool) and 0 < x < self.p and pow(x, self.q, self.p) == 1

    def expoente(self, x: object) -> bool:
        """x é um expoente válido (0 <= x < q)?"""
        return isinstance(x, int) and not isinstance(x, bool) and 0 <= x < self.q

    def aleatorio(self) -> int:
        """Número secreto em [1, q-1], do gerador criptográfico do sistema operacional."""
        return secrets.randbelow(self.q - 1) + 1

    def impressao_digital(self) -> str:
        """Hash curto dos 3 números, pra conferir de olho que dois arquivos usam o mesmo grupo."""
        dados = b"".join(x.to_bytes(BITS_P // 8, "big") for x in (self.p, self.q, self.g))
        return hashlib.sha256(dados).hexdigest()


def gerar_grupo(semente: str = SEMENTE) -> Grupo:
    """Refaz o grupo do zero, só com a semente pública. Mesma semente → mesmos números."""
    # 1. q: o primeiro número de 256 bits (saído do hash) que for primo
    contador = 0
    while True:
        q = _expande(semente, "q", contador, BITS_Q) | (1 << (BITS_Q - 1)) | 1
        if eh_primo(q):
            break
        contador += 1
    # 2. p = k·q + 1: começa num k tirado do hash e anda de 2 em 2 até p dar primo
    #    (k par → p ímpar; p - 1 é múltiplo de q por construção)
    k = (_expande(semente, "p", 0, BITS_P) | (1 << (BITS_P - 1))) // q
    k += k % 2
    while True:
        p = k * q + 1
        if math.gcd(p, _PRIMORIAL) == 1 and eh_primo(p):
            break
        k += 2
    # 3. g = h^((p-1)/q): joga qualquer h pra dentro do subgrupo de ordem q
    contador = 0
    while True:
        h = 2 + _expande(semente, "g", contador, BITS_P) % (p - 3)
        g = pow(h, (p - 1) // q, p)
        if g != 1:
            return Grupo(p, q, g)
        contador += 1


def valida_grupo(grupo: Grupo) -> list[str]:
    """Lista de problemas do grupo (lista vazia = grupo bom)."""
    p, q, g = grupo.p, grupo.q, grupo.g
    problemas = []
    if p.bit_length() != BITS_P:
        problemas.append(f"p tem {p.bit_length()} bits, devia ter {BITS_P}")
    if q.bit_length() != BITS_Q:
        problemas.append(f"q tem {q.bit_length()} bits, devia ter {BITS_Q}")
    if not eh_primo(q):
        problemas.append("q não é primo")
    if not eh_primo(p):
        problemas.append("p não é primo")
    if (p - 1) % q:
        problemas.append("q não divide p - 1")
    if not (1 < g < p) or pow(g, q, p) != 1:
        problemas.append("g não gera o subgrupo de ordem q")
    return problemas


# Gerado com gerar_grupo(SEMENTE). Confira: python3 grupo.py
GRUPO = Grupo(
    p=int(
        (
            "e9a3b56d6ef54366a31245ec05c3b4dc86302d347bced127a4f7feb8f122a2b34e11c3229b3efe362051a39bfa8b1322"
            "694c862c3ce352cadaa8e106abdb8cbfe051fed810607daf03e41b097b8ac8e268e4278eb8813a4621e8cf417c2ce6ec"
            "f609d7857a0372143c52165cc9405c8c0a26fe63c1a812d92ffd83aa27f7b5ad08a6e27d92dd6fab32b03fffeb245ee1"
            "c055a6491f83a49abc2826ce5a4878977caff6be927a58e6802ca50228d8a6e672be15e98430bcd15e34de5b8c91a4e6"
            "e19e21efa13473e939911d9f2cf424eee14cb1ee8b35f5d7f8af69534a3b72a546719733a998dbf67b94e17277012b0b"
            "d512dbc660537c25937f29bb5037c07419d6792f4dadb7c55303a220c2bab06eac6e7fcef04553d0f00c7a0a305669dc"
            "311b9fa8e1ba5d23f52b44e28d0ec7a4b457c217eb70e2b46226ba4708c5984aaea5250665cffe2dad6222409dbab565"
            "47af004f6c5ec595d15b0730ca10b3eed3257341a2e57787a428dcee34b294aaea8e46cbfc1928de188a0e51ecafd041"
        ),
        16,
    ),
    q=int("ddae1696a91498bd1ccfc7014efb4b02c8f7713c792f706a7411e105263a8b3b", 16),
    g=int(
        (
            "e4628b1ee33eec979d55a66762c14cc6e4a79144c43eea5c5cccd443628104105f9ea88402ca723e2af26dba259a82f7"
            "f57edf6807d775a46a8a50e19504b23728802fefe3e4473c14f640b771d0717f866f7927d1f2668cd444616ac27d4de4"
            "da1e498a496f4c71cac673862f0d863538bf320e6c1e896cca7a3c908ea8389eff7d83e70e0efe616846e4296e72adc4"
            "29ca0cc424a75920dff6196931d81d0c9ea56f06676fd5abedd3a379566a571b4247a3ce6ca28d19881d55541f6cad9c"
            "e89a138ea2abe276b88d19fc5b609bc46dc0804367fc384c7d1198ee0d6c1356e4c0ad1e44b76d3800775e614981589e"
            "b30e7e47bcc66e08f33699ff4a2c209a8d11c12901133d7ba5de66e093fca80957c72d48f4dadd535e4d94c242755f81"
            "d77c9242b72af210d4ebf822c6dfb6bbb3578731cb164c42d76fdd35bcc7dcb19bb04642326e1b9b4e442c63b5509910"
            "09536b0d6360d133bb50e0fc9a28cd868c8a319346190b5ffff4749cc4b047e9a99f2a1ff4f77517139f9fe3fe2e4bec"
        ),
        16,
    ),
)
# SHA-256 de p, q e g (384 bytes cada, big-endian). Publicada no README e no PROTOCOLO pra conferir de olho.
IMPRESSAO_DIGITAL = "122c6a8920fbbee3fde975fb2194b84c2672dfd482a855daa7ce998a28250e8f"


def main() -> int:
    print(f'Refazendo o grupo a partir da semente: "{SEMENTE}"')
    novo = gerar_grupo()
    for nome in ("p", "q", "g"):
        valor = getattr(novo, nome)
        igual = valor == getattr(GRUPO, nome)
        situacao = "✓ igual ao do código" if igual else "✗ DIFERENTE"
        print(f"  {nome}: {valor.bit_length():4} bits  {hex(valor)[:26]}…  {situacao}")
    problemas = valida_grupo(GRUPO)
    for problema in problemas:
        print(f"  ✗ {problema}")
    digital = novo.impressao_digital()
    if digital != IMPRESSAO_DIGITAL:
        print(f"  ✗ impressão digital {digital} não é a publicada")
    if novo != GRUPO or problemas or digital != IMPRESSAO_DIGITAL:
        return 1
    print(f"✓ grupo reproduzido e validado · impressão digital {digital}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
