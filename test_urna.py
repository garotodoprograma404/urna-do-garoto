import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import ataques as A
import guardioes as GU
import urna as U
import verificador as V
from grupo import GRUPO

AQUI = Path(__file__).resolve().parent


def quieto(mural: dict, ata: dict | None = None, ate: int = 7) -> list[str]:
    return V.verifica(mural, saida=lambda _: None, paralelo=False, ata=ata, ate=ate)


def relacra(mural: dict) -> dict:
    mural["lacre"] = U.lacre(mural)
    return mural


class TestEleicao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = A.eleicao()

    def test_eleicao_honesta_confere(self):
        self.assertEqual(quieto(self.c.mural), [])
        self.assertEqual(quieto(self.c.mural, self.c.ata), [])

    def test_resultado_e_o_que_os_eleitores_escolheram(self):
        esperado = Counter(A.ESCOLHAS["secao-001"]) + Counter(A.ESCOLHAS["secao-002"])
        self.assertEqual(self.c.mural["apuracao"]["resultado"], {o: esperado[o] for o in A.OPCOES})

    def test_desafiadas_nao_contam_e_conferem(self):
        desafiadas = [r for r in self.c.mural["cedulas"] if r["estado"] == U.DESAFIADA]
        self.assertEqual([r["abertura"]["escolha"] for r in desafiadas], list(A.DESAFIAM.values()))
        for reg in desafiadas:
            cifrou = V.confere_abertura(self.c.mural["contexto"], self.c.chave, A.OPCOES, reg)
            self.assertEqual(cifrou, reg["abertura"]["escolha"])

    def test_salva_e_carrega(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "mural.json"
            mural = copy.deepcopy(self.c.mural)
            U.salva(mural, caminho)
            self.assertEqual(quieto(V.carrega(str(caminho), "o mural"), self.c.ata), [])

    def test_recibo_confirmado(self):
        codigo, _, ficha = self.c.recibos[4]
        recibo, minha = U.codigo_curto(codigo), U.ficha_impressa(ficha)
        self.assertEqual(len(recibo.replace("-", "")), 32)
        self.assertTrue(V.confere_recibo(self.c.mural, recibo, ficha=minha)[0])
        self.assertTrue(V.confere_recibo(self.c.mural, codigo, ficha=minha)[0])  # o QR code: o código inteiro
        ok, mensagem = V.confere_recibo(self.c.mural, recibo, desafiei=True, ficha=minha)
        self.assertFalse(ok)  # ele confirmou; se dissesse que desafiou, o mural desmente
        self.assertFalse(V.confere_recibo(self.c.mural, "0" * 32)[0])
        self.assertFalse(V.confere_recibo(self.c.mural, recibo.replace("-", "")[:20])[0])  # recibo inteiro, sempre
        self.assertFalse(V.confere_recibo(self.c.mural, recibo.replace("-", "")[:16])[0])
        self.assertFalse(V.confere_recibo(self.c.mural, "AB")[0])

    def test_recibo_com_a_ficha_de_outro(self):
        codigo, _, _ = self.c.recibos[4]
        _, _, outra = self.c.recibos[5]
        ok, mensagem = V.confere_recibo(self.c.mural, U.codigo_curto(codigo), ficha=U.ficha_impressa(outra))
        self.assertFalse(ok)
        self.assertIn("OUTRO eleitor", mensagem)
        ok, mensagem = V.confere_recibo(self.c.mural, U.codigo_curto(codigo))  # sem a ficha: confere, mas avisa
        self.assertTrue(ok)
        self.assertIn("--ficha", mensagem)

    def test_recibo_desafiado_mostra_o_que_a_urna_cifrou(self):
        reg = next(r for r in self.c.mural["cedulas"] if r["estado"] == U.DESAFIADA)
        ok, mensagem = V.confere_recibo(self.c.mural, U.codigo_curto(reg["codigo"]), desafiei=True)
        self.assertTrue(ok)
        self.assertIn(reg["abertura"]["escolha"], mensagem)
        self.assertFalse(V.confere_recibo(self.c.mural, U.codigo_curto(reg["codigo"]))[0])

    def test_recibos_repetidos(self):
        r = U.codigo_curto(self.c.recibos[0][0])
        self.assertEqual(
            V.recibos_repetidos([r, r.lower().replace("-", ""), U.codigo_curto(self.c.recibos[1][0])]),
            [r.lower().replace("-", "")],
        )
        self.assertEqual(V.recibos_repetidos([U.codigo_curto(cod) for cod, _, _ in self.c.recibos]), [])

    def test_lacre(self):
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"]["recusados"] = ["Fiscal do Partido B"]  # passa em todo o resto: só o lacre pega
        self.assertEqual(
            quieto(mural, self.c.ata), ["o lacre do mural não bate (o arquivo foi mexido depois de lacrado)"]
        )

    def test_ata_de_outra_eleicao(self):
        ata = copy.deepcopy(self.c.ata)
        ata["contexto"] = "0" * 64
        self.assertTrue(quieto(self.c.mural, ata))

    def test_ata_com_urna_a_mais(self):
        ata = copy.deepcopy(self.c.ata)
        ata["urnas"]["secao-999"] = ata["urnas"]["secao-001"]
        self.assertTrue(any("secao-999" in p for p in quieto(self.c.mural, ata)))

    def test_ata_com_contas_da_urna_erradas(self):
        for campo, valor in (("depositadas", 13), ("sem_voto", 1), ("depositadas", "banana")):
            ata = copy.deepcopy(self.c.ata)
            ata["urnas"]["secao-001"][campo] = valor
            with self.subTest(campo=campo, valor=valor):
                self.assertTrue(quieto(self.c.mural, ata))

    def test_ata_parcial(self):
        ata = copy.deepcopy(self.c.ata)
        del ata["urnas"]["secao-002"]
        v = V.Verificador(self.c.mural, saida=lambda _: None, paralelo=False, ata=ata, ata_parcial=True)
        self.assertEqual(v.roda(), [])
        self.assertEqual(v.sem_porta, ["secao-002"])

    def test_recibo_em_mural_forjado(self):
        mural = copy.deepcopy(self.c.mural)
        codigo, _, _ = self.c.recibos[0]
        reg = next(r for r in mural["cedulas"] if r["codigo"] == codigo)
        reg["cifras"][1][1] = U.hx(int(reg["cifras"][1][1], 16) * A.G % A.P)
        self.assertFalse(V.confere_recibo(mural, U.codigo_curto(codigo))[0])

    def test_ata_sem_uma_secao(self):
        ata = copy.deepcopy(self.c.ata)
        del ata["urnas"]["secao-002"]
        self.assertTrue(any("ata" in p for p in quieto(self.c.mural, ata)))

    def test_mural_mal_formado_vira_problema_e_nao_explosao(self):
        estragos = [
            lambda m: m["cedulas"][0]["cifras"][0].__setitem__(0, "nao-e-hex"),
            lambda m: m["cedulas"][0]["cifras"][0].__setitem__(0, "00" + m["cedulas"][0]["cifras"][0][0]),
            lambda m: m.__setitem__("chave", "f" * 5000),
            lambda m: m["cedulas"].insert(0, 7),
            lambda m: m["cedulas"][0].__setitem__("id", [[[["fundo"]]]]),
            lambda m: m["cedulas"][0].__setitem__("ficha", "nao-e-ficha"),
            lambda m: m["manifesto"].__setitem__("quorum", True),
            lambda m: m["urnas"].__setitem__("secao-001", None),
            lambda m: m["urnas"]["secao-001"].__setitem__("devolvidas", -1),
            lambda m: m["apuracao"]["resultado"].__setitem__("Pastel", True),
            lambda m: m.__setitem__("cedulas", "nada"),
            lambda m: m["cedulas"][0].__setitem__("cpf", "123.456.789-00"),  # campo fora do protocolo
            lambda m: m["grupo"].__setitem__("cpf", "123.456.789-00"),
            lambda m: m.__setitem__("extra", 1),
            lambda m: m["manifesto"].__setitem__("quorum", 1),
            lambda m: m.__setitem__("manifesto", []),
        ]
        for estraga in estragos:
            mural = copy.deepcopy(self.c.mural)
            estraga(mural)
            relacra(mural)  # quem estraga também relacra: quem pega tem que ser outra checagem
            with self.subTest(estraga=estraga):
                self.assertTrue(quieto(mural))
                self.assertTrue(quieto(mural, self.c.ata))

    def test_ficha_usada_duas_vezes(self):
        mural = copy.deepcopy(self.c.mural)
        a, b = A.depositada(mural, 0), A.depositada(mural, 1)
        b["ficha"] = a["ficha"]  # duas sessões com a mesma ficha: cédula enfiada?
        A.refaz(self.c, mural)
        self.assertTrue(any("já tinha sido usada" in p for p in quieto(mural)))

    def test_conferencia_dos_guardioes_antes_da_apuracao(self):
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"] = None
        self.assertEqual(quieto(mural, self.c.ata, ate=5), [])

    # as checagens que nenhum golpe exercitava sozinhas (desligar uma tem que deixar algum teste vermelho)
    def test_depositada_com_segredo_exposto(self):
        mural = copy.deepcopy(self.c.mural)
        A.depositada(mural, 0)["abertura"] = {"escolha": "Pastel", "segredos": ["1"] * len(A.OPCOES)}
        relacra(mural)
        self.assertTrue(any("segredos expostos" in p for p in quieto(mural, self.c.ata)))

    def test_recusados_sem_sentido(self):
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"]["recusados"] = ["Universidade"]  # ela está entre os presentes
        relacra(mural)
        self.assertTrue(any("recusados" in p for p in quieto(mural, self.c.ata)))

    def test_copia_aparece_como_copia(self):
        _, pegos = A.ataca(self.c, A.repeticao)
        self.assertTrue(any("cifra copiada" in p for p in pegos))

    def test_fatia_forjada_pelo_totalizador(self):
        problemas = quieto(A.fatia_forjada_pelo_totalizador(self.c), self.c.ata)
        self.assertTrue(any("não tem prova válida" in p for p in problemas))

    def test_cifra_com_segredo_zero(self):
        mural = copy.deepcopy(self.c.mural)
        reg = A.depositada(mural, 0)
        ctx, rid, k = mural["contexto"], reg["id"], self.c.chave
        votos, rs = [1, 0, 0, 0], [0] + [GRUPO.aleatorio() for _ in range(3)]
        cifras = [A.C.cifra(k, v, r) for v, r in zip(votos, rs, strict=True)]
        provas = [
            A.C.prova_zero_ou_um((ctx, rid, i), k, cf, v, r)
            for i, (cf, v, r) in enumerate(zip(cifras, votos, rs, strict=True))
        ]
        soma = A.C.prova_soma((ctx, rid), k, cifras[0] * cifras[1] * cifras[2] * cifras[3], 1, sum(rs) % GRUPO.q)
        reg["cifras"] = [[U.hx(cf.alfa), U.hx(cf.beta)] for cf in cifras]
        reg["provas"] = [[U.hx(p.c0), U.hx(p.c1), U.hx(p.v0), U.hx(p.v1)] for p in provas]
        reg["prova_soma"] = [U.hx(soma.c), U.hx(soma.v)]
        self.assertTrue(any("voto está em claro" in p for p in quieto(mural)))


class TestJsonESaida(unittest.TestCase):
    def test_chave_repetida_e_recusada(self):
        with self.assertRaises(ValueError):
            V.le_json('{"resultado": {"Pastel": 0}, "resultado": {"Pastel": 9}}')
        self.assertEqual(V.le_json('{"a": {"b": 1}}'), {"a": {"b": 1}})

    def test_limpo_tira_escape_de_terminal(self):
        sujo = "x\x1b[2J\x1b[H✓ tudo confere\x1b[8m\r\n"
        self.assertNotIn("\x1b", V.limpo(sujo))
        self.assertNotIn("\r", V.limpo(sujo))
        self.assertIn("✓ tudo confere", V.limpo(sujo))

    def test_linha_de_comando(self):
        c = A.eleicao()
        with tempfile.TemporaryDirectory() as pasta:
            caminho, ata = Path(pasta) / "mural.json", Path(pasta) / "ata.json"
            mural = copy.deepcopy(c.mural)
            mural["manifesto"]["eleicao"] = "x\x1b[2J\x1b[H✓ tudo confere\x1b[8m"  # injeção de terminal
            relacra(mural)
            caminho.write_text(json.dumps(mural, ensure_ascii=False), encoding="utf-8")
            ata.write_text(json.dumps(c.ata), encoding="utf-8")
            ambiente = {**os.environ, "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"}
            roda = [sys.executable, str(AQUI / "verificador.py"), str(caminho), "--ata", str(ata)]
            r = subprocess.run(roda, capture_output=True, text=True, env=ambiente)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("\x1b", r.stdout)
            self.assertNotIn("Traceback", r.stderr)
            mural["manifesto"] = []
            caminho.write_text(json.dumps(mural, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run(roda, capture_output=True, text=True, env=ambiente)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)
            U.salva(copy.deepcopy(c.mural), caminho)
            r = subprocess.run([*roda, "--contexto", "0" * 64], capture_output=True, text=True, env=ambiente)
            self.assertEqual(r.returncode, 1)
            r = subprocess.run([*roda, "--contexto", c.mural["contexto"]], capture_output=True, text=True, env=ambiente)
            self.assertEqual(r.returncode, 0, r.stdout)


class TestUrna(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = A.eleicao()

    def nova(self) -> U.Urna:
        return U.Urna("secao-002", self.c.manifesto, self.c.mural["contexto"], self.c.chave)

    def test_ordem_das_coisas(self):
        urna = self.nova()
        with self.assertRaises(U.ErroUrna):
            urna.prepara("Esfiha")  # a mesa não liberou a cabine
        ficha = U.nova_ficha()
        urna.libera(ficha)
        with self.assertRaises(U.ErroUrna):
            urna.libera(U.nova_ficha())  # já tem sessão aberta
        with self.assertRaises(U.ErroUrna):
            urna.confirma()  # nada preparado
        urna.prepara("Esfiha")
        with self.assertRaises(U.ErroUrna):
            urna.prepara("Pastel")  # já tem cédula esperando
        with self.assertRaises(U.ErroUrna):
            urna.fecha()  # cédula pendente
        urna.confirma()
        with self.assertRaises(U.ErroUrna):
            urna.libera(ficha)  # ficha já usada
        with self.assertRaises(U.ErroUrna):
            urna.libera("nao-e-ficha")
        urna.fecha()
        with self.assertRaises(U.ErroUrna):
            urna.libera(U.nova_ficha())  # urna fechada

    def test_opcao_inexistente(self):
        urna = self.nova()
        urna.libera(U.nova_ficha())
        with self.assertRaises(U.ErroUrna):
            urna.prepara("Coxinha de jaca")

    def test_urna_fora_do_manifesto(self):
        with self.assertRaises(U.ErroUrna):
            U.Urna("secao-999", self.c.manifesto, self.c.mural["contexto"], self.c.chave)

    def test_codigo_sai_antes_da_decisao_e_e_o_mesmo(self):
        urna = self.nova()
        urna.libera(U.nova_ficha())
        codigo = urna.prepara("Pastel")
        self.assertEqual(urna.confirma(), codigo)
        self.assertEqual(urna.registros[-1]["codigo"], codigo)

    def test_confirmada_nao_guarda_segredo(self):
        urna = self.nova()
        urna.libera(U.nova_ficha())
        urna.prepara("Pastel")
        urna.confirma()
        self.assertIsNone(urna.registros[-1]["abertura"])

    def test_chave_invalida(self):
        for chave in (2**3071, 1, GRUPO.p - 1):
            with self.assertRaises(U.ErroUrna):
                U.Urna("secao-001", self.c.manifesto, self.c.mural["contexto"], chave)

    def test_cabine_confere_o_codigo_impresso(self):
        urna = self.nova()
        ficha = U.nova_ficha()
        urna.libera(ficha)
        impresso = urna.prepara("BRANCO")
        urna.desafia()
        reg, ctx = urna.registros[-1], self.c.mural["contexto"]
        self.assertIsNone(V.confere_desafio_na_cabine(ctx, self.c.chave, A.OPCOES, reg, impresso, "BRANCO", ficha))
        self.assertIn("na tela", V.confere_desafio_na_cabine(ctx, self.c.chave, A.OPCOES, reg, impresso, "Pastel"))
        outro = "0" * 64
        self.assertIn("OUTRA cédula", V.confere_desafio_na_cabine(ctx, self.c.chave, A.OPCOES, reg, outro, "BRANCO"))
        _, pegos = A.troca_no_desafio(self.c)
        self.assertTrue(any("OUTRA cédula" in p for p in pegos))

    def test_desistencia_nao_vira_fraude(self):
        """Eleitor que desafia e vai embora, e um fiscal que testa a urna: a mesa anota as fichas devolvidas,
        a urna grava SEM_VOTO, e a eleição honesta confere e abre."""
        manifesto = self.c.manifesto
        guardioes, chave = GU.cerimonia_das_chaves(list(A.GUARDIOES), A.QUORUM, U.pre_contexto(manifesto))
        mural = U.novo_mural(manifesto, [g.compromissos for g in guardioes], chave)
        ata = {"versao": U.VERSAO, "contexto": mural["contexto"], "urnas": {}}
        for ident, escolhas in (("secao-001", ("Pastel", "Esfiha")), ("secao-002", ("BRANCO",))):
            urna = U.Urna(ident, manifesto, mural["contexto"], chave)
            for e in escolhas:
                urna.libera(U.nova_ficha())
                urna.prepara(e)
                urna.confirma()
            urna.libera(U.nova_ficha())
            urna.prepara("Pastel")
            urna.desafia()
            urna.encerra_sem_voto()  # desafiou e foi embora
            urna.libera(U.nova_ficha())
            urna.prepara("Esfiha")
            urna.encerra_sem_voto()  # largou a cédula sem decidir: aberta como desafiada, nunca conta
            fecho = urna.fecha()
            U.publica_urna(mural, ident, urna.registros, fecho, len(escolhas) + 2, devolvidas=2)
            ata["urnas"][ident] = U.ata_da_secao(fecho, len(escolhas) + 2, devolvidas=2)
        self.assertEqual(quieto(mural, ata, ate=5), [])
        for g in guardioes:
            g.recebe_ata(ata)
        self.assertEqual(U.apura(mural, guardioes[:3]), {"Pastel": 1, "Pão de queijo": 0, "Esfiha": 1, "BRANCO": 1})
        self.assertEqual(quieto(relacra(mural), ata), [])
        mesa_sem_anotar = copy.deepcopy(ata)
        mesa_sem_anotar["urnas"]["secao-001"]["devolvidas"] = 0
        self.assertTrue(any("devolvidas" in p for p in quieto(mural, mesa_sem_anotar)))

    def test_voto_jogado_fora_como_sem_voto(self):
        _, pegos = A.joga_fora(self.c)
        self.assertTrue(any("devolvidas" in p for p in pegos))
        self.assertTrue(any("jogou teu voto fora" in p for p in pegos))

    def test_clash_pego_pela_ficha(self):
        feito, pegos = A.clash(self.c)
        self.assertIn("todo recibo confere em casa", feito)  # sem a ficha, ninguém perceberia
        self.assertTrue(any("OUTRO eleitor" in p for p in pegos))
        self.assertTrue(any("recibos repetidos" in p or "recibo repetido" in p for p in pegos))

    def test_apuracao_sem_quorum_ou_repetida(self):
        mural = copy.deepcopy(self.c.mural)
        with self.assertRaises(U.ErroUrna):
            U.apura(mural, self.c.guardioes[:2])
        with self.assertRaises(U.ErroUrna):
            U.apura(mural, [self.c.guardioes[0]] * 3)

    def test_guardioes_nao_abrem_mural_que_nao_confere(self):
        mural = copy.deepcopy(self.c.mural)
        mural["cedulas"].pop(3)
        mural["apuracao"] = None
        with self.assertRaises(U.ErroUrna):
            U.apura(mural, A.frescos(self.c))

    def test_guardiao_nao_usa_ata_de_quem_pede(self):
        forjado, ata_forjada = A.mural_de_um_voto(self.c)
        self.assertEqual(quieto(forjado, ata_forjada, ate=5), [])  # com a ata forjada, o mural "confere"
        with self.assertRaises(U.ErroUrna):
            U.apura(forjado, A.frescos(self.c))  # mas cada guardião confere com a ata DELE
        _, motivos = A.abre_uma_cedula(self.c)
        self.assertEqual(len(motivos), len(A.GUARDIOES) + 1)  # nenhum guardião honesto abriu

    def test_guardiao_abre_uma_soma_so(self):
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"] = None
        g = A.frescos(self.c, 1)[0]
        primeira = g.abre_apuracao(mural)
        self.assertEqual(g.abre_apuracao(mural), primeira)  # a MESMA soma: mesmas fatias, nada novo
        forjado, ata_forjada = A.mural_de_um_voto(self.c)
        g.recebe_ata(ata_forjada)  # nem se a ata dele estivesse errada: outra soma, nunca
        with self.assertRaises(GU.ErroCerimonia):
            g.abre_apuracao(forjado)

    def test_guardiao_ruim_no_primeiro_quorum_nao_trava_a_eleicao(self):
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"] = None
        g1, g2, g3, g4, g5 = A.frescos(self.c, 5)
        with self.assertRaises(U.ErroUrna):
            U.apura(mural, [g1, g2, A.Vendido(g4)])
        self.assertEqual(U.apura(mural, [g1, g2, g3, g5]), self.c.mural["apuracao"]["resultado"])

    def test_guardiao_sem_ata_nao_abre(self):
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"] = None
        g = A.frescos(self.c, 1)[0]
        g._ata = None  # os fiscais dele não trouxeram a ata
        with self.assertRaises(GU.ErroCerimonia):
            g.abre_apuracao(mural)

    def test_guardiao_de_outra_eleicao_nao_abre(self):
        outra = A.eleicao(apura=False)
        mural = copy.deepcopy(self.c.mural)
        mural["apuracao"] = None
        g = A.frescos(outra, 1)[0]
        g.recebe_ata(self.c.ata)
        with self.assertRaises(GU.ErroCerimonia):
            g.abre_apuracao(mural)


if __name__ == "__main__":
    unittest.main()
