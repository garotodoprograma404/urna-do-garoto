import secrets
import unittest

import cripto as C
import guardioes as GU
from grupo import GRUPO, IMPRESSAO_DIGITAL, Grupo, gerar_grupo, valida_grupo

P, Q, G = GRUPO.p, GRUPO.q, GRUPO.g
VETOR_INICIO = "1203ed2df92b429479ac04b9e2824b8923f4eafd2029420d16b297b2d2be69ff"
VETOR_ELO = "846d517ef26fe00927efd8e635d4ce306fe96c6269691fc0e8e97bbab22a855c"
VETOR_HQ = "ca33ea2a96bae2032ee7e8b09a0a2c30754cbb5b470062f1bcee84cfb2c5541e"


def par_de_chaves() -> tuple[int, int]:
    s = GRUPO.aleatorio()
    return s, C.potencia(G, s)


class TestGrupo(unittest.TestCase):
    def test_grupo_valido(self):
        self.assertEqual(valida_grupo(GRUPO), [])

    def test_grupo_sai_da_semente(self):
        # sem isso, trocar o GRUPO por outro grupo válido (até um com alçapão) deixaria tudo verde (~25 s)
        self.assertEqual(gerar_grupo(), GRUPO)
        self.assertEqual(GRUPO.impressao_digital(), IMPRESSAO_DIGITAL)

    def test_valida_grupo_pega_grupo_ruim(self):
        self.assertTrue(valida_grupo(Grupo(P, Q, 1)))
        self.assertTrue(valida_grupo(Grupo(P, Q, P - 1)))  # ordem 2
        self.assertTrue(valida_grupo(Grupo(P, Q, 2)))  # 2 não está no subgrupo de ordem q
        self.assertTrue(valida_grupo(Grupo(P, Q + 2, G)))

    def test_pertence_recusa_quem_e_de_fora(self):
        self.assertTrue(C.pertence(G))
        self.assertFalse(C.pertence(P - 1))  # ordem 2: o clássico ataque de subgrupo pequeno
        self.assertFalse(C.pertence(0))
        self.assertFalse(C.pertence(P))
        self.assertFalse(C.pertence(True))
        self.assertFalse(C.pertence("2"))
        self.assertFalse(C.pertence(2))  # está em Z_p*, mas não no subgrupo de ordem q
        ordem_7457 = pow(3, (P - 1) // 7457, P)  # p - 1 = 2^6 · 7457 · … · q: subgrupos pequenos existem
        self.assertNotEqual(ordem_7457, 1)
        self.assertFalse(C.pertence(ordem_7457))
        with self.assertRaises(ValueError):
            C.fixa(P - 1)

    def test_base_fixa_da_o_mesmo_que_pow(self):
        _, k = par_de_chaves()
        C.fixa(k)
        for e in [0, 1, Q - 1, Q, Q + 5, *(secrets.randbelow(Q) for _ in range(20))]:
            self.assertEqual(C.potencia(k, e), pow(k, e, P))


class TestHash(unittest.TestCase):
    def test_codificacao_sem_ambiguidade(self):
        self.assertNotEqual(C.hash_hex("t", "ab", "c"), C.hash_hex("t", "a", "bc"))
        self.assertNotEqual(C.hash_hex("t", 0), C.hash_hex("t", b"\x00"))
        self.assertNotEqual(C.hash_hex("t", [1, 2]), C.hash_hex("t", 1, 2))
        self.assertNotEqual(C.hash_hex("t", 1), C.hash_hex("u", 1))

    def test_recusa_bool_e_negativo(self):
        with self.assertRaises(TypeError):
            C.codifica(True)
        with self.assertRaises(ValueError):
            C.codifica(-1)

    def test_hash_q_fica_no_intervalo(self):
        for i in range(50):
            self.assertTrue(0 <= C.hash_q("t", i) < Q)

    def test_vetores_do_protocolo(self):
        # os mesmos da tabela "Vetores de teste" do PROTOCOLO.md: se um mudar, a spec e o código divergiram
        self.assertEqual(C.codifica(0).hex(), "490000000100")
        self.assertEqual(C.codifica(256).hex(), "49000000020100")
        self.assertEqual(C.codifica("Pão").hex(), "530000000450c3a36f")
        self.assertEqual(C.codifica([1, "a"]).hex(), "4c00000002490000000101530000000161")
        self.assertEqual(C.hash_hex("inicio", "0" * 64, "secao-001"), VETOR_INICIO)
        self.assertEqual(C.hash_hex("elo", "0" * 64, "ab", "DEPOSITADA"), VETOR_ELO)
        self.assertEqual(format(C.hash_q("soma", ["0" * 64, "secao-001/000001"], 2, 3), "x"), VETOR_HQ)


class TestCifra(unittest.TestCase):
    def test_soma_sem_abrir(self):
        s, k = par_de_chaves()
        votos = [1, 0, 1, 1, 0, 1]
        total = C.CIFRA_ZERO
        for v in votos:
            total = total * C.cifra(k, v, GRUPO.aleatorio())
        g_m = total.beta * pow(total.alfa, Q - s, P) % P
        self.assertEqual(C.log_pequeno(g_m, len(votos)), sum(votos))


class TestProvas(unittest.TestCase):
    def setUp(self):
        _, self.k = par_de_chaves()
        self.ctx = ("teste", "cedula-1", 0)

    def test_zero_ou_um_aceita_0_e_1(self):
        for m in (0, 1):
            r = GRUPO.aleatorio()
            cf = C.cifra(self.k, m, r)
            prova = C.prova_zero_ou_um(self.ctx, self.k, cf, m, r)
            self.assertTrue(C.confere_zero_ou_um(prova, self.ctx, self.k, cf))
            self.assertFalse(C.confere_zero_ou_um(prova, ("outro",), self.k, cf))  # presa ao contexto

    def test_zero_ou_um_recusa_dois(self):
        with self.assertRaises(ValueError):
            C.prova_zero_ou_um(self.ctx, self.k, C.cifra(self.k, 2, 5), 2, 5)
        r = GRUPO.aleatorio()
        honesta = C.prova_zero_ou_um(self.ctx, self.k, C.cifra(self.k, 1, r), 1, r)
        dois = C.cifra(self.k, 2, r)  # mesma aleatoriedade, voto 2: a prova não serve
        self.assertFalse(C.confere_zero_ou_um(honesta, self.ctx, self.k, dois))

    def test_zero_ou_um_recusa_numero_fora_do_intervalo(self):
        r = GRUPO.aleatorio()
        cf = C.cifra(self.k, 1, r)
        p = C.prova_zero_ou_um(self.ctx, self.k, cf, 1, r)
        torta = C.ProvaZeroOuUm(p.c0 + Q, p.c1, p.v0, p.v1)  # mesmo valor mod q, fora do intervalo
        self.assertFalse(C.confere_zero_ou_um(torta, self.ctx, self.k, cf))
        self.assertFalse(C.confere_zero_ou_um(p, self.ctx, self.k, C.Cifra(cf.alfa, P - 1)))

    def test_soma(self):
        rs = [GRUPO.aleatorio() for _ in range(3)]
        total = C.cifra(self.k, 0, rs[0]) * C.cifra(self.k, 1, rs[1]) * C.cifra(self.k, 0, rs[2])
        prova = C.prova_soma(self.ctx, self.k, total, 1, sum(rs) % Q)
        self.assertTrue(C.confere_soma(prova, self.ctx, self.k, total, 1))
        self.assertFalse(C.confere_soma(prova, self.ctx, self.k, total, 2))
        self.assertFalse(C.confere_soma(prova, self.ctx, self.k, total, 0))

    def test_conhecimento(self):
        x = GRUPO.aleatorio()
        publico = C.potencia(G, x)
        prova = C.prova_conhecimento("ctx", publico, x)
        self.assertTrue(C.confere_conhecimento(prova, "ctx", publico))
        self.assertFalse(C.confere_conhecimento(prova, "ctx", publico * G % P))
        self.assertFalse(C.confere_conhecimento(prova, "outro", publico))

    def test_cifra_sem_segredo_e_recusada(self):
        cf = C.cifra(self.k, 1, 0)  # r = 0: alfa = 1 e beta = g, qualquer um lê o voto no mural
        self.assertFalse(C.confere_zero_ou_um(C.prova_zero_ou_um(self.ctx, self.k, cf, 1, 0), self.ctx, self.k, cf))

    def test_fiat_shamir_forte_recusa_copia_rerandomizada(self):
        r, t = GRUPO.aleatorio(), GRUPO.aleatorio()
        cf = C.cifra(self.k, 1, r)
        p = C.prova_zero_ou_um(self.ctx, self.k, cf, 1, r)
        copia = C.Cifra(cf.alfa * C.potencia(G, t) % P, cf.beta * C.potencia(self.k, t) % P)
        torta = C.ProvaZeroOuUm(p.c0, p.c1, (p.v0 + t * p.c0) % Q, (p.v1 + t * p.c1) % Q)
        self.assertFalse(C.confere_zero_ou_um(torta, self.ctx, self.k, copia))  # com FS fraco, passaria
        self.assertFalse(C.confere_zero_ou_um(p, self.ctx, self.k * G % P, cf))  # presa à chave

    def test_verificadores_recusam_malformados(self):
        x = GRUPO.aleatorio()
        h1, a = C.potencia(G, x), C.potencia(G, GRUPO.aleatorio())
        h2 = pow(a, x, P)
        boa = C.prova_igualdade("decifra", "ctx", G, h1, a, h2, x)
        self.assertTrue(C.confere_igualdade(boa, "decifra", "ctx", G, h1, a, h2))
        for ruim in (-1, Q, Q + boa.c, True, 1.0, "1", None):
            self.assertFalse(C.confere_igualdade(C.ProvaIgualdade(ruim, boa.v), "decifra", "ctx", G, h1, a, h2))
            self.assertFalse(C.confere_igualdade(C.ProvaIgualdade(boa.c, ruim), "decifra", "ctx", G, h1, a, h2))
        for fora in (0, P - 1, P, P + 1, -1, 2, True, None, h2 * (P - 1) % P):
            self.assertFalse(C.confere_igualdade(boa, "decifra", "ctx", G, h1, a, fora))
            self.assertFalse(C.confere_conhecimento(C.prova_conhecimento("c", h1, x), "c", fora))


class TestGuardioes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nomes = ["A", "B", "C", "D", "E"]
        cls.guardioes, cls.chave = GU.cerimonia_das_chaves(cls.nomes, 3, "pre")
        cls.compromissos = [g.compromissos for g in cls.guardioes]

    def abre(self, quem: list[int], cf: C.Cifra, ctx: str) -> int | None:
        fatias = []
        for i in quem:
            g = self.guardioes[i]
            verificacao = GU.chave_de_verificacao(self.compromissos, g.numero)
            fatia = g._decifra(ctx, 0, cf)
            self.assertTrue(GU.confere_fatia(fatia, ctx, 0, verificacao, cf))
            fatias.append(fatia)
        return C.log_pequeno(cf.beta * pow(GU.combina(fatias), -1, P) % P, 10)

    def test_quaisquer_tres_abrem(self):
        cf = C.cifra(self.chave, 7, GRUPO.aleatorio())
        self.assertEqual(self.abre([0, 1, 2], cf, "tres"), 7)
        self.assertEqual(self.abre([4, 2, 3], cf, "tres"), 7)
        self.assertEqual(self.abre([0, 1, 2, 3, 4], cf, "tres"), 7)

    def test_dois_nao_abrem(self):
        cf = C.cifra(self.chave, 1, GRUPO.aleatorio())
        self.assertIsNone(self.abre([0, 4], cf, "dois"))

    def test_guardiao_recusa_numero_de_fora_do_grupo(self):
        with self.assertRaises(GU.ErroCerimonia):
            self.guardioes[1]._decifra("fora", 0, C.Cifra(P - 1, 1))  # ordem 2: vazaria 1 bit do segredo

    def test_fatia_falsa_na_cerimonia(self):
        honesto, outro = GU.Guardiao(1, "x", 3, "pre"), GU.Guardiao(2, "y", 3, "pre")
        self.assertFalse(outro.recebe_fatia(honesto.compromissos, (honesto.fatia_para(2) + 1) % Q))
        self.assertTrue(outro.recebe_fatia(honesto.compromissos, honesto.fatia_para(2)))

    def test_fatia_conferida_contra_outro_guardiao_nao_passa(self):
        cf = C.cifra(self.chave, 1, GRUPO.aleatorio())
        g = self.guardioes[0]
        fatia = g._decifra("troca", 0, cf)
        self.assertFalse(GU.confere_fatia(fatia, "troca", 0, GU.chave_de_verificacao(self.compromissos, 2), cf))

    def test_quorum_invalido(self):
        with self.assertRaises(ValueError):
            GU.cerimonia_das_chaves(["A", "B"], 3, "pre")
        with self.assertRaises(ValueError):
            GU.cerimonia_das_chaves(["A", "B"], 1, "pre")  # quórum 1: cada guardião abriria tudo sozinho
        dois = [GU.Guardiao(1, "A", 1, "pre"), GU.Guardiao(2, "B", 1, "pre")]
        with self.assertRaises(ValueError):
            GU.cerimonia(dois, 1, "pre")  # a porta de entrada dos ataques também confere

    def test_compromissos_presos_ao_guardiao(self):
        a = GU.Guardiao(1, "A", 3, "pre")
        copia = GU.Compromissos(2, "B", a.compromissos.coeficientes, a.compromissos.provas)  # B copia os do A
        self.assertFalse(GU.confere_compromissos(copia, "pre", 3))
        curto = GU.Compromissos(1, "A", a.compromissos.coeficientes[:2], a.compromissos.provas[:2])
        self.assertFalse(GU.confere_compromissos(curto, "pre", 3))  # grau menor
        self.assertFalse(GU.confere_compromissos(a.compromissos, "outro-pre", 3))  # outra eleição


if __name__ == "__main__":
    unittest.main()
