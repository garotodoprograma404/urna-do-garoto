# O hardware da Urna do Garoto;

> A matemática (o código deste repositório) garante que **fraude na contagem aparece**.
> O hardware cuida do que a matemática não alcança: **o instante em que você aperta a tecla**.

Este documento é uma proposta de projeto, não uma máquina pronta. Cada peça vem com **o quê**, **pra quê** e o **caso real** que ensinou por que ela precisa existir.

Várias dessas ideias já existem em urnas e equipamentos reais pelo mundo, inclusive na urna brasileira: ela não tem rede, tem módulo de segurança e só roda programa assinado. A proposta junta tudo num desenho só e deixa cada escolha explicada.

---

## A regra de ouro

**Cada aparelho faz uma coisa só, e nenhum aparelho confere a si mesmo.**

```
  MESA (identifica o eleitor)          CABINE (vota)                         FORA DA URNA
 ┌──────────────────────────┐      ┌──────────────────────────────┐     ┌──────────────────────────┐
 │ biometria / documento    │      │ tela + teclas físicas        │     │ celular do eleitor ou    │
 │ conta fichas e devolvidas│──┐   │ módulo criptográfico (chip)  │     │ do fiscal: confere o     │
 │ NÃO tem cabo com a urna  │  │   │ impressora do recibo         │     │ DESAFIO (app aberto)     │
 └──────────────────────────┘  │   │ CONFIRMA  |  DESAFIA         │     │                          │
                               │   └──────────────┬───────────────┘     │ qualquer computador:     │
       ficha de uso único  ────┘                  │ mídia + elo final   │ confere o MURAL inteiro  │
       (não diz quem é você)                      ▼ impresso na porta   │ (verificador.py)         │
                                           MURAL PÚBLICO ──────────────▶│                          │
                                                                        └──────────────────────────┘
```

---

## As peças

### 1. Nenhum rádio. Nenhum.
- **O quê:** sem Wi-Fi, Bluetooth, celular, NFC ou porta de rede. Gabinete blindado (gaiola de Faraday) e teclado e tela de baixa emissão.
- **Pra quê:** não existe ataque pela rede se não existe rede. E a blindagem impede que alguém **escute** o voto pelo ar.
- **Caso real:** **Holanda, 2006.** Pesquisadores captaram, pelo rádio, em quem a pessoa votava numa urna Nedap sem nenhuma modificação, a vários metros de distância; nas urnas da Sdu, o serviço de inteligência holandês captou a 20–30 m. O país voltou ao lápis e papel em 2008.

### 2. Só liga programa assinado por **k de n** entidades
- **O quê:** um chip de raiz de confiança confere a assinatura do sistema antes de ligar. A assinatura é **dividida**: precisa de, por exemplo, 3 de 5 entidades (Justiça Eleitoral, universidade, OAB, fiscais de partidos rivais). É a mesma ideia dos guardiões do código (`guardioes.py`), aplicada ao software.
- **Pra quê:** nenhuma entidade sozinha, nem quem fabrica a urna, consegue instalar um programa novo.
- **Caso real:** **Holanda, 2006.** Trocar **2 chips de memória** na placa trocava o programa da urna inteira. Os pesquisadores fizeram a urna jogar xadrez.

### 3. Compilação reproduzível + o hash na tela
- **O quê:** o código é público. Qualquer pessoa compila e chega **exatamente nos mesmos bytes** (*reproducible build*, como fazem o Debian e o Tor). Ao ligar, a urna mostra o hash do sistema que está rodando, e o fiscal confere com um app.
- **Pra quê:** responde a pergunta que todo fiscal do mundo faz: *"o código que eu inspecionei é o mesmo que está rodando aqui?"*
- **Caso real:** é a dúvida mais comum em fiscalização de sistema eleitoral em qualquer país. Sem compilação reproduzível, a resposta é "confia".

### 4. Módulo criptográfico separado (o "cofre" dentro da urna)
- **O quê:** um chip à parte, do tipo dos módulos de segurança de banco, faz toda a criptografia. Ele gera os segredos de cada cédula, cifra, assina e **apaga tudo** da memória logo depois. A tela só manda a escolha e recebe o código.
- **Pra quê:** reduz a área de ataque. O sistema da tela pode ter um bug, mas os segredos não passam por ele.
- **Caso real:** é o padrão de qualquer maquininha de cartão e de qualquer cofre de chaves de banco (FIPS 140-3).

### 5. Gerador de números aleatórios de verdade, com exame de saúde
- **O quê:** a fonte de aleatoriedade é física (ruído elétrico) e passa por testes contínuos (NIST SP 800-90B). Se a fonte "viciar", a urna **para**.
- **Pra quê:** toda a segurança do voto cifrado depende de os segredos serem imprevisíveis.
- **Caso real:** **Debian, 2008 (CVE-2008-0166).** Uma linha de código removida por engano fez o OpenSSL gerar só **32.768** chaves possíveis durante quase dois anos. Dava pra testar todas em minutos.

### 6. Impressora do recibo que imprime ANTES de liberar os botões
- **O quê:** a urna imprime o código de confirmação, e **só depois** os botões CONFIRMA e DESAFIA acendem. A ordem é garantida pelo circuito, não pelo software. O recibo leva **só o código** (32 dígitos) e o QR code (o código inteiro), **nunca o voto**.
- **Pra quê:** é o que faz o desafio de Benaloh funcionar. A urna se compromete antes de saber se vai ser desafiada.
- **E depois do botão:** a impressora acrescenta no mesmo papel a decisão (CONFIRMADA ou DESAFIADA). Em casa, o código de quem confirmou tem que aparecer no mural como **DEPOSITADA** e com a **ficha** dele. Se aparecer como desafiada, a urna trocou a cédula depois do botão (golpe 09 do `ataques.py`); se aparecer com a ficha de outro, a urna deu a ele o recibo de outro eleitor (golpe 19). Nos dois casos, o eleitor tem o papel na mão pra reclamar.
- **Caso real:** é o desenho dos sistemas verificáveis testados em eleições reais (Takoma Park, EUA, 2009; ElectionGuard, 2020–2023).

### 7. Quem confere o desafio é OUTRO aparelho
- **O quê:** o app (no celular do eleitor ou do fiscal) lê o QR do código **antes** do DESAFIA. Depois do desafio, a urna entrega a cédula aberta, e o app confere que ela é **a do código impresso** e da ficha dele, e que os segredos refazem as cifras com a opção da tela. Sem conferir o código, a urna troca a cédula na hora do desafio e abre uma honesta (golpe 18).
- **Pra quê:** uma máquina que confere a si mesma não prova nada.
- **Caso real:** **Argentina, 2015.** Na "boleta única electrónica", a conferência do chip da cédula era feita **pela mesma máquina** que gravou o voto, e pesquisadores acharam o ataque "multivoto" (um chip com vários votos), que tinha passado por auditorias anteriores.

### 8. O fiscal desafiador
- **O quê:** além do eleitor, os fiscais de cada partido podem fazer **votos-teste desafiados** a qualquer hora do dia, sem aviso. É a votação paralela, só que na urna de verdade e na hora de verdade. O fiscal pega a ficha do **mesmo saco** que o eleitor (a urna não sabe quem é), desafia **com o candidato dele** e, às vezes, **duas ou três vezes seguidas**, e no fim a mesa anota a ficha como devolvida.
- **Pra quê:** a matemática do desafio precisa de gente desafiando, e de um jeito que a urna não consiga prever. Se 1 em cada 10 cédulas com aquele voto for desafiada, uma urna que tente trocar 100 votos tem **1 chance em 37.649** de escapar. E a urna sabe que a cédula logo depois de um desafio costuma ser o voto de verdade: só o desafio duplo pega quem trapaceia ali (golpe 21).
- **Caso real:** **Michigan, 2020.** Num estudo com 241 pessoas, a máquina trocava o voto impresso, e só **6,6%** avisaram o mesário. Esperar que o eleitor confira sozinho não basta: alguém tem que ter esse trabalho.

### 9. A identificação fica na mesa, sem cabo com a urna
- **O quê:** a mesa identifica o eleitor (biometria, documento) num aparelho separado, e ele **sorteia às cegas** uma ficha de uso único de um saco embaralhado (a mesa não anota quem pegou qual). A ficha só libera a cabine, não diz quem é você, e entra no código do recibo. A mesa conta as **fichas liberadas** e as **devolvidas sem voto** (desistência ou teste do fiscal), e **não guarda ordem nem hora**: o mural publica as cédulas na ordem em que foram feitas, e a ordem da fila ligaria cada pessoa à cédula cifrada dela. A urna nunca sabe quem está votando.
- **Pra quê:** é o que pega o golpe de **encher a urna** (golpe 06 do `ataques.py`): cédula a mais que eleitor contado pela mesa aparece na hora, mesmo que o vilão reescreva o comparecimento dentro do mural, porque o número que vale é o da **ata assinada pela mesa**. E separar quem você é do que você vota protege o sigilo.

### 10. Memória que só aceita escrever no fim, em dois lugares
- **O quê:** o mural da seção vai pra uma memória que **não deixa apagar nem reescrever** (WORM). No fechamento, o **elo final** (o hash que resume a seção inteira) sai impresso e é colado na porta, e os fiscais fotografam.
- **Pra quê:** trocar o mural depois exige trocar o papel de todas as portas fotografadas. O verificador confere o mural contra essa ata (`--ata`).

### 11. Lacres que denunciam e chip que se apaga
- **O quê:** lacres que mostram se foram violados, e um sensor de abertura que **apaga as chaves do aparelho** se alguém abrir a urna (como nos cofres de chave dos bancos, níveis 3 e 4 da FIPS 140-3).
- **Pra quê:** quem abre a urna escondido fica com uma caixa inútil e deixa rastro.

### 12. A chave da apuração nunca existe inteira
- **O quê:** a chave que abre a soma nasce dividida entre os guardiões (`guardioes.py`), e cada parte fica num token de hardware **com cópia de segurança**. Precisa de 3 de 5.
- **Pra quê:** ninguém sozinho abre nada, e perder uma parte não para a eleição.
- **Casos reais:** **IACR, 2025.** A associação internacional de criptógrafos anulou a própria eleição porque **um dos 3 guardiões perdeu a chave** (e eles exigiam os 3). **Basileia, Suíça, 2026:** **2.048 votos** eletrônicos não puderam ser abertos porque o cantão perdeu o acesso aos pen drives protegidos por PIN (a análise oficial fala em manuseio irregular). Com 3 de 5 e cópia, perder uma parte não teria parado a apuração.

### 13. Energia que não cai
- **O quê:** bateria interna de longa duração, além da tomada.
- **Pra quê:** urna que desliga é urna trocada, e troca de urna é momento frágil.
- **Caso real:** **Brasil, 1º turno de 2026 (4/10).** O TSE substituiu 1.861 urnas (menos de 0,4% das 499.248), a maioria por queda de energia; no Paraná, com chuva forte, foi a maior proporção do país (0,72%). Nenhuma seção precisou votar no papel: a urna brasileira já tem bateria, e a troca funcionou.
- **E no protocolo daqui:** urna trocada no meio do dia (contingência) ainda **não tem saída** na v2: a reserva não está no manifesto, e a quebrada não imprime o elo final. A próxima versão lista as reservas de cada seção no manifesto.

### 14. Hardware aberto e peças comuns, de dois fornecedores
- **O quê:** esquemas elétricos publicados, chips de mercado comuns, e cada peça crítica com dois fornecedores.
- **Pra quê:** ninguém fica refém de uma fábrica só, e qualquer universidade consegue montar uma urna de teste e atacar.

### 15. Acessível
- **O quê:** áudio com fone, teclas em braile e fonte grande. O recibo também sai em áudio.
- **Pra quê:** uma urna que só funciona pra quem enxerga não é a urna de todo mundo.

---

## O que NÃO vai na urna
- rede de qualquer tipo;
- disco com o voto em texto claro;
- porta USB ativa durante a votação;
- atualização remota;
- relógio que acerte a hora pela internet.

## O preço (sem esconder)
- **Custa mais.** Impressora, módulo criptográfico e blindagem encarecem cada urna, e são centenas de milhares de urnas.
- **Dá mais trabalho.** Fiscal desafiador, guardiões com token e cerimônia de chaves exigem gente treinada.
- **Não resolve coerção total.** Se alguém está do seu lado na cabine, nenhuma matemática ajuda: isso é com a lei e com a cabine fechada.
- **A urna ainda vê o voto por um instante.** As peças 1, 4 e 11 existem pra que esse instante não vaze. É uma confiança no hardware, não uma prova matemática.

## Cada peça e o código
| Peça | Onde aparece no código |
|---|---|
| 2, 12 | `guardioes.py`: k de n, com prova e fatia conferida |
| 4, 5 | `cripto.py`: cifra, provas e `GRUPO.aleatorio()` (no Python, `secrets`; na urna, o gerador físico) |
| 6, 7, 8 | `urna.py`: `prepara()` devolve o código antes de `confirma()`/`desafia()`; `verificador.confere_desafio_na_cabine()` roda em outro aparelho; o fiscal com desafio duplo em `eleicao.py` |
| 9, 10 | `urna.py` `libera(ficha)`, `encerra_sem_voto()`, `fecha()` e `ata_da_secao()`; o passo 4 do `verificador.py` com `--ata` |
| 6 (depois do botão) | `verificador.py --recibo … --ficha …` (e `--desafiei`); `--recibos` pra coleta pública |
