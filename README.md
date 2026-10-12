# Urna do Garoto;

**Uma urna em que a fraude não fica escondida. Duvida? Roda.**
Feito pelo [Garoto do Programa;](https://instagram.com/garotodoprograma) · Python puro, nada pra instalar.

> **Projeto didático.** Não é a urna do TSE, não foi auditado por terceiros de fora do canal e não deve ser usado em eleição real. Precisa de Python 3.10 ou mais novo.

```bash
python3 eleicao.py                                  # uma eleição inteira: 3 seções × 100 eleitores (~1-3 min)
python3 ataques.py                                  # o vilão tenta 22 golpes (~2-3 min)
python3 verificador.py mural.json --ata ata.json    # confere tudo sozinho, sem confiar em ninguém
python3 verificador.py mural.json --ata ata.json --recibo <seu-recibo> --ficha <sua-ficha>              # eu CONFIRMEI
python3 verificador.py mural.json --ata ata.json --recibo <seu-recibo> --ficha <sua-ficha> --desafiei   # eu DESAFIEI
python3 grupo.py                                    # refaz os números mágicos a partir de uma frase pública (~20-30 s)
python3 -m unittest -v                              # os testes
```

## A ideia em uma frase

Urna 100% impossível de atacar não existe, e quem promete isso está vendendo alguma coisa.
O que existe, e é o que a ciência de eleições busca desde os anos 1980 (e tem nome desde 2006), é **urna em que qualquer fraude deixa rastro**.
Se alguém mexer no software, o resultado não muda **sem que dê pra provar que mudou**.
O nome disso é *independência de software* (Rivest e Wack, NIST, 2006).

Aqui ninguém precisa confiar na urna, no fabricante, no tribunal nem em mim. **Confere.**

## Como funciona, do lado do eleitor

```
 0. na mesa, você      1. você escolhe   2. a urna cifra e IMPRIME o     3. você decide:
    sorteia às cegas      na tela           código ANTES de você            CONFIRMA → vai pro mural, você leva o recibo
    uma FICHA e digita                      decidir (ele amarra a ficha)    DESAFIA  → a urna é obrigada a abrir aquela
    na urna                                 35A0-98D3-AF48-D407-…                      cédula, e o seu celular confere que é
                                            (não diz em quem você votou)               a do código impresso e que cifrou o
                                                                                       que estava na tela. Vota de novo.

 4. em casa: procura o recibo no mural, com a sua ficha. Confirmou? Tem que estar lá como DEPOSITADA e com a SUA ficha.
    Desafiou? Tem que estar como DESAFIADA, e o verificador mostra o que a urna tinha cifrado.
 5. qualquer pessoa baixa o mural e a ata das portas, confere todas as provas e refaz a soma.
```

**Dica:** desafie com **qualquer** opção, não precisa ser a sua. A cédula desafiada fica pública (é o objetivo), e a urna não sabe o que vem depois. E **de vez em quando desafie duas vezes seguidas**: a urna sabe que a cédula logo depois de um desafio costuma ser o voto de verdade.

## O que garante o quê

| Garantia | Como | Onde |
|---|---|---|
| Ninguém vê o seu voto | cada opção é cifrada (ElGamal) e a apuração abre **só a soma**, nunca uma cédula | `cripto.py`, `urna.py` |
| Não dá pra enfiar 50 votos numa cédula | prova de conhecimento zero de que cada cifra esconde **0 ou 1** | `cripto.py` |
| Não dá pra votar em dois | prova de que a soma da cédula é **exatamente 1** | `cripto.py` |
| A urna não consegue trocar seu voto sem risco | ela imprime o código **antes** de saber se você vai desafiar; no desafio, o celular confere que a cédula aberta é a do código impresso; em casa, você confere que a sua está **depositada** e com a **sua ficha** | `urna.py`, `verificador.py` |
| Sumiu ou entrou cédula? Aparece | corrente de hashes por seção + **ata fora do mural** (elo final colado na porta, fichas liberadas e devolvidas assinadas pela mesa) | `urna.py`, `verificador.py` |
| Eleitor que desiste não vira "fraude" | a sessão sem voto entra na corrente (SEM_VOTO) e a mesa anota a ficha devolvida | `urna.py`, `verificador.py` |
| Ninguém inventa nem some com uma seção | a lista de urnas é fechada e publicada **antes**, no manifesto (e a cerimônia dos guardiões amarra o manifesto) | `verificador.py` |
| Ninguém sozinho abre a urna | a chave nasce dividida entre 5 guardiões e precisa de 3 | `guardioes.py` |
| Perderam uma chave? Segue o jogo | 3 de 5: o Garoto perdeu a dele (não tem mão) e a apuração abriu igual. E um guardião ruim na primeira tentativa não trava a eleição | `guardioes.py` |
| Guardião não vira máquina de abrir voto | confere o mural contra a ata que **ele mesmo** recebeu dos fiscais (nunca a que vem junto do pedido), calcula a soma ele mesmo e abre **uma** soma na vida | `guardioes.py` |
| Resultado anunciado = soma de verdade | cada guardião prova que usou a parte certa, e qualquer um refaz a conta (e o número tem que estar entre 0 e o total) | `verificador.py` |
| Nem os números mágicos foram escolhidos por mim | o grupo de 3072 bits sai do hash de uma frase pública; impressão digital `122c6a8920fbbee3fde975fb2194b84c2672dfd482a855daa7ce998a28250e8f` | `grupo.py` |

## Rodando uma eleição

Trecho da saída (os números mudam a cada rodada):

```
[2/6] cerimônia das chaves: 5 guardiões, abre com 3
   ✓ Universidade           publicou 3 compromissos com prova e conferiu as 5 fatias
   ✓ Imprensa               publicou 3 compromissos com prova e conferiu as 5 fatias
   ✓ Fiscal do Partido A    publicou 3 compromissos com prova e conferiu as 5 fatias
   ✓ Fiscal do Partido B    publicou 3 compromissos com prova e conferiu as 5 fatias
   ✓ Garoto do Programa;    publicou 3 compromissos com prova e conferiu as 5 fatias
   chave da eleição: 690ad0b8da04a1e6f09dbe5c…  (ninguém tem ela inteira. Nem eu.)

[3/6] votação: 3 seções × 100 eleitores = 300 votos
   cada eleitor sorteia uma ficha e tem 10% de chance de DESAFIAR (uma vez, opção qualquer)
   antes de cada eleitor, 3% de chance de um fiscal testar a urna (2 ou 3 desafios seguidos)
   300 cédulas cifradas e provadas em 30 s
   42 desafios (6 testes de fiscal): a urna abriu a cédula do código impresso,
   e o celular conferiu que ela cifrou o que estava na tela
      secao-001/000007: na tela 'Pão de queijo' → a cédula do código impresso tinha isso  ✓
   recibo de um eleitor: 262F-DD67-DB66-9F5E-AC02-BC18-80FA-D2EF  ficha 0B1E-6E78-A7E1-CC43  (não diz em quem ele votou)

[4/6] fechamento: a ata (elo final na porta + fichas da mesa), fora do mural
   secao-001: 100 cédulas · 4 sem voto · 104 fichas da mesa (4 devolvidas) · elo final 04199e7c68918dde

[5/6] apuração: os guardiões abrem SÓ a soma
   Garoto do Programa; perdeu a chave dele. (Ele não tem mão.) Sem problema: precisa de 3.
   Pastel            111  ███████████████
   Pão de queijo      96  █████████████
   Esfiha             68  █████████
   BRANCO             25  ███
   o que os eleitores escolheram de verdade (só a simulação sabe): bate ✓

[6/6] verificador (não importa urna.py; dá pra escrever o seu pelo PROTOCOLO.md)
      ✓ p de 3072 bits e q de 256 bits, primos, iguais aos do grupo.py (--paranoico refaz); impressão digital 122c6a8920fbbee3…
      ✓ 5 guardiões, cada um provou a sua parte; abre com 3
      ✓ 342 cédulas: 0 ou 1 em cada opção, soma 1, nenhuma cópia
      ✓ 3 urnas do manifesto, corrente inteira, 300 cédulas = 300 eleitores, 6 fichas sem voto e com a ata das portas
      ✓ 42 desafios: os segredos abrem cada cédula desafiada (quem desafiou confere se é a opção que viu na tela)
      ✓ multipliquei as cifras das depositadas de novo: dá a soma publicada
      ✓ 3 guardiões abriram a soma, cada fatia com prova: Pastel 111 · Pão de queijo 96 · Esfiha 68 · BRANCO 25
   ✓ eleitor em casa, recibo 262F-DD67-DB66-9F5E-AC02-BC18-80FA-D2EF, ficha 0B1E-6E78-A7E1-CC43: recibo encontrado: secao-001/000024 DEPOSITADA. Tua cédula está lá, cifrada, e entra na soma.
```

A eleição é de mentira (o lanche da firma), mas a matemática é de verdade.

## Os 22 golpes (`python3 ataques.py`)

Os mais perigosos são os de **dentro**: a própria urna trapaceando, refazendo a corrente inteira, reescrevendo o comparecimento do mural e chamando guardiões cúmplices pra abrir a soma de novo.

| # | Golpe | Quem pega |
|---|---|---|
| 01 | troco um voto já depositado (e ajusto soma, resultado e lacre) | prova "0 ou 1" + o código do recibo não bate |
| 02 | apago uma cédula | corrente quebrada + cédula faltando na sequência |
| 03 | sou a urna: 5 votos numa cédula só | prova "0 ou 1" |
| 04 | sou a urna: voto em dois, com provas 0-ou-1 válidas | prova "soma = 1" |
| 05 | copio a cédula cifrada de alguém (pra descobrir o voto pela diferença) | provas presas à cédula + cifra repetida |
| 06 | sou a urna: encho com 5 cédulas perfeitas e reescrevo o comparecimento | a ata: 17 cédulas × 12 eleitores assinados pela mesa |
| 07 | viro uma cédula desafiada em voto | a ata: 13 cédulas × 12 eleitores, e o elo final não é o da porta |
| 08 | sou a urna: troco Pastel por Esfiha ANTES de cifrar | quem desafia, com o celular conferindo o código impresso (a urna troca TODO Pastel: o fiscal do Pastel pega sempre; o eleitor, por estatística) |
| 09 | sou a urna: troco DEPOIS do CONFIRMA (o mural fica perfeito) | o eleitor em casa: confirmei e está como desafiada |
| 10 | invento uma seção inteira | não está no manifesto |
| 11 | sumo com uma seção inteira | a seção do manifesto sumiu |
| 12 | anuncio Pastel −2, Esfiha +2 | a soma cifrada abre outro número |
| 13 | resultado que "dá a volta no relógio" (+q num, −q no outro) | número fora de 0 a total |
| 14 | guardião vendido entrega fatia falsa | a prova da fatia não fecha: recusado, e os outros 3 abrem (e se o totalizador publicar a fatia forjada, o verificador recusa) |
| 15 | peço pros guardiões abrirem um mural com uma cédula só | mesmo com uma ata forjada que bate com o mural, cada guardião confere contra a ata que recebeu dos fiscais dele: nenhum abre |
| 16 | dois guardiões juntam os segredos pra abrir um voto | não funciona: 2 guardiões não abrem nada (precisa de 3) |
| 17 | chave pirata: guardião escolhe a parte dele depois de ver as dos outros | a prova de Schnorr não fecha (e as fatias dele não batem com o compromisso) |
| 18 | sou a urna: no DESAFIA, jogo fora a cédula trocada e abro uma honesta | o celular confere que a cédula aberta é a do código impresso |
| 19 | sou a urna: dou pra dois eleitores que votaram igual o MESMO recibo e troco o voto do segundo (*clash*) | a ficha: o recibo está lá, mas com a ficha de outro (e a coleta pública acha recibo repetido) |
| 20 | sou a urna: jogo um voto fora como se o eleitor tivesse desistido | a mesa não anotou ficha devolvida (e, com mesário cúmplice, o recibo + ficha do eleitor) |
| 21 | sou a urna: trapaceio só na cédula logo depois de um desafio | o fiscal que desafia duas vezes seguidas |
| 22 | escondo um resultado falso no arquivo do mural (chave repetida no JSON) | o verificador recusa JSON com chave repetida |

**Achou um golpe que passa? Abre uma issue com o código pra reproduzir.** Se passar, ele vira teste. É pra isso que o código é aberto.

## Auditoria antes de publicar (12/10/2026)

O vídeo mostra 17 golpes. Antes de o código ir a público, uma auditoria independente (criptografia, protocolo e repositório, em separado) achou **mais 5** que passavam. Eles viraram os golpes 18 a 22, e **todos são pegos agora**:

- **18:** a urna trocava a cédula na hora do desafio, porque o celular só conferia os segredos, e não o código impresso. Agora confere.
- **19:** *clash* (Küsters, Truderung e Vogt, 2012): dois eleitores com o mesmo recibo, e o recibo em casa não pegava. Agora a **ficha** sorteada às cegas entra no código.
- **20:** sem saída pra quem desiste, um eleitor que desafiava e ia embora travava a apuração do país. Agora a sessão sem voto entra na corrente, e a mesa anota a ficha devolvida. Isso abria um golpe novo, que é a urna jogar um voto fora "como desistência", e esse golpe também é pego.
- **21:** a urna sabia que a cédula logo depois de um desafio é o voto de verdade. Agora o fiscal desafia duas vezes seguidas.
- **22:** um JSON com chave repetida mostrava um resultado falso pra quem lia o arquivo, com o mesmo lacre. Agora é recusado.

E 4 dos 17 originais foram reforçados:

- **golpe 15:** os guardiões aceitavam a ata que vinha junto do pedido. Com uma ata forjada, 3 guardiões honestos abriam o voto de um eleitor. Agora cada um usa a ata dos fiscais dele.
- **golpe 08:** era pego "por sorte" da semente.
- **golpe 14:** agora também testa o totalizador que publica uma fatia forjada.
- **guardião ruim na primeira tentativa:** travava a apuração pra sempre. Agora pedir a mesma soma de novo devolve as mesmas fatias.

Também: o recibo subiu de 20 pra **32 dígitos**, e o verificador ficou mais duro com arquivo estranho (campo a mais, escape de terminal, recibo pela metade).

## A conta que assusta o vilão

A urna não sabe quem vai desafiar. Se ela troca `k` votos e cada cédula **com aquele voto** é desafiada com chance `d`, a chance de ela **nunca** ser pega é `(1 − d)^k`.

| votos trocados | chance de escapar se d = 5% | se d = 10% |
|---|---|---|
| 10 | 60% | 35% |
| 100 | 0,6% (1 em 169) | **0,003% (1 em 37.649)** |
| 1.000 | 1 em 1,9 × 10²² | 1 em 5,7 × 10⁴⁵ |

Roubar pouco às vezes passa. Roubar o suficiente pra virar uma eleição não passa, **desde que**:
- **o desafio seja imprevisível.** Se quem desafia escolhe a opção ao acaso, o `d` cai na proporção (1 ÷ nº de opções) ÷ (fatia do candidato roubado). E se todo mundo desafia uma vez só, a urna trapaceia na cédula seguinte sem risco (golpe 21);
- **o fiscal de cada partido desafie com o candidato DELE, o dia inteiro, às vezes duas vezes seguidas** (ver [HARDWARE.md](HARDWARE.md)). É ele que segura a conta;
- **conferir o recibo em casa é outra conta:** pega troca no mural (golpes 09, 19 e 20), mas não pega a troca feita antes de cifrar. Essa só o desafio pega.

## O que a matemática NÃO resolve (sem esconder)

- **A urna vê o voto no instante em que você digita.** Isso não se resolve com prova, e sim com hardware: sem rádio, chip separado, memória apagada e lacres. Ver [HARDWARE.md](HARDWARE.md).
- **Precisa de gente desafiando e conferindo o recibo com a ficha.** Uma eleição verificável que ninguém verifica não prova nada. Sem a ficha, o recibo em casa não pega o *clash* (golpe 19).
- **A ordem do mural é a ordem da fila.** Quem anotar a ordem de quem entrou na cabine liga cada pessoa à cédula cifrada dela. Isso não abre o voto (continua cifrado), mas 3 guardiões juntos (ou um computador quântico no futuro) abririam o voto de uma pessoa **específica**, e quem desafia com a própria opção mostra o voto. Por isso a mesa não guarda ordem nem hora, só a contagem, e a dica é desafiar com uma opção qualquer.
- **3 guardiões juntos abrem qualquer cédula.** Por isso os guardiões são de lados rivais: universidade, imprensa e fiscais de partidos adversários.
- **Coerção na cabine.** Se alguém está do seu lado mandando, a matemática não ajuda. O recibo não prova em quem você votou, então não serve pra vender voto.
- **A ata não tem assinatura digital.** O elo final colado na porta e as contas assinadas pela mesa só protegem se chegarem a você, e a cada guardião, pelas fotos dos fiscais, por um caminho que o coordenador da apuração não controla. O verificador confia na ata que você passar: com uma ata vinda de quem montou o mural, ele diria "confere" pra uma urna enchida. Anote o `contexto` publicado antes da eleição e use `--contexto`; se você só tem as fotos de algumas seções, use `--ata-parcial`. Sem `--ata`, o verificador não diz "tudo confere".
- **O recibo não é assinado pela urna.** Um eleitor mal-intencionado pode inventar uma reclamação. O papel original da impressora e a contagem de reclamações por urna resolvem na prática; a assinatura do aparelho fica pra próxima versão.
- **Urna que quebra no meio do dia (contingência).** Ainda não tem saída no protocolo: a urna reserva não está no manifesto, e a quebrada não imprime o elo final. O verificador acusa a seção. A próxima versão lista as reservas de cada seção no manifesto.
- **O verificador usa as mesmas peças da urna.** Ele não importa `urna.py`, mas usa `cripto.py` e `guardioes.py`, as mesmas que a urna e os guardiões usam pra provar: um bug nelas engana os dois. Por isso o PROTOCOLO.md tem vetores de teste. Um verificador independente de verdade é **outro programa**, escrito por outra pessoa.
- **Canal subliminar.** Uma urna maliciosa pode esconder bits do voto na aleatoriedade das cifras e das provas. O Fiat-Shamir forte garante que a prova é válida, não que é "limpa". Mitigação: hardware auditado. Aleatoriedade verificável fica pra próxima versão.
- **A cerimônia é o DKG de Pedersen (1991), com o segredo verificável de Feldman (1987).** Quem publica por último ainda pode enviesar um pouquinho a chave final (Gennaro, Jarecki, Krawczyk e Rabin, 1999); a versão sem viés fica pra próxima. E se um guardião acusa outro de mandar fatia falsa, a cerimônia para sem saber quem mentiu (falta a fase de reclamação). Aqui as fatias andam na memória; na vida real viajam cifradas, cada uma só pro dono.
- **Computador quântico.** No futuro, um computador quântico grande quebraria o logaritmo discreto e poderia abrir votos antigos guardados. A integridade da eleição de hoje não muda, mas o sigilo eterno é pesquisa em aberto.
- **Este código é didático.** Não foi auditado por terceiros de fora do canal, e o Python não faz conta em tempo constante (vaza tempo). Numa urna de verdade, a criptografia roda num chip feito pra isso. **Não use em eleição real.**

## Escreve o seu verificador

O [PROTOCOLO.md](PROTOCOLO.md) tem tudo pra conferir um mural **sem ler uma linha do meu código**: o grupo, os hashes, as provas, o formato do JSON e da ata, os 7 passos, o desafio, o recibo, as regras do guardião e os **vetores de teste**.
Escreve em Rust, Go, JavaScript, o que for. Se o seu e o meu disserem OK, você não precisa confiar em nenhum dos dois.

## Arquivos

| arquivo | o quê |
|---|---|
| `grupo.py` | o grupo de 3072 bits, gerado de uma semente pública |
| `cripto.py` | cifra, soma cifrada e as provas (Schnorr, Chaum-Pedersen, 0-ou-1) |
| `guardioes.py` | a chave dividida: cerimônia, fatias conferidas, apuração com k de n |
| `urna.py` | a urna (libera com a ficha, prepara, confirma, desafia, encerra sem voto, fecha), o mural, a ata e a apuração |
| `verificador.py` | o verificador (não importa `urna.py`), a conferência na cabine e a do recibo em casa |
| `eleicao.py` | uma eleição inteira, do grupo ao veredito |
| `ataques.py` | os 22 golpes |
| `AMEACAS.md` | o modelo de ameaças: cada etapa do voto, cada ataque e o que pega |
| `HARDWARE.md` | o que a urna física precisa ter, e por quê |
| `PROTOCOLO.md` | a especificação, pra você escrever o seu verificador |

## De onde vêm as peças (nada aqui é invenção minha)

- ElGamal (1985); a versão exponencial pra votação vem de Cramer, Gennaro e Schoenmakers (1997).
- Chaum e Pedersen, *Wallet Databases with Observers* (1992).
- Cramer, Damgård e Schoenmakers, *Proofs of Partial Knowledge* (1994): a prova "0 ou 1".
- Schnorr (1989) · Fiat e Shamir (1986).
- Feldman (1987) e Pedersen (1991): segredo dividido e verificável. Gennaro, Jarecki, Krawczyk e Rabin (1999): o viés.
- Benaloh, *Simple Verifiable Elections* (2006): o desafio.
- Rivest e Wack (NIST, 2006) e Rivest (2008): independência de software.
- Bernhard, Pereira e Warinschi, *How not to prove yourself* (2012): por que o hash do Fiat-Shamir inclui **tudo**.
- Cortier e Smyth (2011): o ataque da cédula copiada.
- Küsters, Truderung e Vogt, *Clash Attacks on the Verifiability of E-Voting Systems* (IEEE S&P 2012): por que o recibo precisa da ficha.
- ElectionGuard (Benaloh, Naehrig, Pereira e Wallach, USENIX Security 2024): a arquitetura que mais inspirou este projeto.
- National Academies, *Securing the Vote* (2018).

MIT · Garoto do Programa;
