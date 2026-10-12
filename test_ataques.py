import unittest

import ataques as A

# O que tem que aparecer em algum "PEGO" de cada golpe: a defesa que o README diz que pega. Assim um golpe
# não vira "pego" por acaso (por uma checagem que não é a dele) sem o teste ficar vermelho.
QUEM_PEGA = {
    A.troca_voto: 'prova "0 ou 1"',
    A.apaga: "cédula sumiu",
    A.turbinada: 'prova "0 ou 1"',
    A.voto_duplo: 'prova "soma = 1"',
    A.repeticao: "cifra copiada",
    A.enche_urna: "na ata da mesa",
    A.vira_desafiada: "na ata da mesa",
    A.urna_trapaceira: "a urna cifrou 'Esfiha'",
    A.troca_depois_do_botao: "você CONFIRMOU",
    A.urna_fantasma: "não está no manifesto",
    A.some_secao: "sumiu do mural",
    A.resultado_falso: "a soma cifrada abre",
    A.volta_no_relogio: "fora de 0 a",
    A.fatia_falsa: "não tem prova válida",
    A.abre_uma_cedula: "ata dos meus fiscais",
    A.conluio: "dois guardiões não abrem nada",
    A.chave_pirata: "prova de conhecimento inválida",
    A.troca_no_desafio: "OUTRA cédula",
    A.clash: "OUTRO eleitor",
    A.joga_fora: "devolvida",
    A.pos_desafio: "o fiscal, no desafio seguido",
    A.resultado_escondido: "chave repetida",
}


class TestAtaques(unittest.TestCase):
    """Todo golpe tem que ser pego, e pela defesa certa. Se um dia um passar, o teste fica vermelho."""

    @classmethod
    def setUpClass(cls):
        cls.c = A.eleicao()

    def test_sao_22(self):
        # 01 a 17: os do vídeo (mesmos números e títulos). 18 a 22: os da auditoria antes de publicar.
        self.assertEqual(len(A.ATAQUES), 22)
        self.assertEqual(A.ATAQUES[14][0], "Peço pros guardiões abrirem uma cédula só")
        self.assertEqual(set(QUEM_PEGA), {funcao for _, funcao in A.ATAQUES})

    def test_cada_golpe_e_pego(self):
        for titulo, funcao in A.ATAQUES:
            with self.subTest(golpe=titulo):
                _, pegos = A.ataca(self.c, funcao)
                self.assertTrue(pegos, f"o golpe passou: {titulo}")
                self.assertTrue(any(QUEM_PEGA[funcao] in p for p in pegos), f"{titulo}: pego por outra coisa: {pegos}")

    def test_urna_trapaceira_nao_depende_da_semente(self):
        # Trocando TODO Pastel, o fiscal do Pastel (que pega ficha como qualquer um) pega a urna sempre,
        # em qualquer semente. As sementes 3 e 8 eram as que escapavam na versão antiga do golpe 08.
        for semente in (3, 8):
            feito, pegos = A.urna_trapaceira(self.c, eleitores=30, semente=semente)
            with self.subTest(semente=semente):
                self.assertTrue(any("fiscal do Pastel" in p for p in pegos), feito)

    def test_roubar_pouco_as_vezes_passa(self):
        # Sem fiscal, trocando só 1 em cada 4 Pastéis, a urna às vezes escapa: é estatística (README, a conta).
        feito, pegos = A.urna_trapaceira(
            self.c, eleitores=30, chance_desafio=0.4, semente=SEMENTE_ESCAPA, chance_troca=0.25, fiscal_a_cada=0
        )
        self.assertNotIn("(0 votos trocados", feito)
        self.assertEqual(pegos, [])


SEMENTE_ESCAPA = 2

if __name__ == "__main__":
    unittest.main()
