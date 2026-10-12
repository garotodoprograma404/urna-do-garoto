# Modelo de ameaças da Urna do Garoto;

> Todo sistema de votação sério começa aqui: **a lista de todo jeito de atacar, e o que pega cada um.**
> Este documento segue o voto do dedo do eleitor até o resultado publicado, etapa por etapa. Em cada etapa:
> **o ataque · como funciona · quem faz · o que o nosso desenho pega (e onde) · o risco que sobra.**
>
> A regra que organiza tudo é uma só: **independência de software** (Rivest & Wack, 2006). A gente **assume que
> o software, a rede e os computadores estão infectados** e projeta pra que, mesmo assim, uma fraude não mude o
> resultado sem deixar rastro que qualquer um confere. Segurança não é "ninguém ataca"; é "todo ataque aparece".

---

## 0. Quem é o atacante (modelo de adversário)

Não adianta se defender de hacker de filme e esquecer o de dentro. A gente assume que o atacante pode ser **qualquer um destes, inclusive vários ao mesmo tempo**:

| Atacante | O que ele controla |
|---|---|
| **Fabricante da urna** | o hardware e o firmware, antes de tudo |
| **Programador de dentro** (do órgão eleitoral) | o código-fonte, antes de ser assinado |
| **Operador / técnico** no dia | a carga da urna, a mídia, a transmissão |
| **Mesário** | quem entra na cabine, a liberação da urna |
| **Fiscal de partido** | acesso de fiscalização, presença física |
| **Guardião da chave** | uma parte da chave de apuração |
| **Coordenador da totalização** | o computador que soma e publica |
| **Atacante de rede** | o caminho entre a urna e a totalização |
| **Atacante físico** | acesso à urna antes, durante ou depois |
| **Estado-nação** | grana, TEMPEST, cadeia de suprimentos, 0-day |
| **Eleitor malicioso** | o próprio voto, e mentir depois ("defaming") |

**Premissa central:** não existe peça confiável sozinha. A confiança vem de **peças que se vigiam** — adversários mútuos (partidos rivais, universidade, imprensa) e **qualquer cidadão com o verificador**. Onde a gente precisa confiar em alguém, isso está escrito em letra garrafal na seção de risco.

O que a gente **não** tenta resolver (e diz na cara): coerção de quem está do seu lado dentro da cabine, e o dia em que um computador quântico grande existir. Está tudo na seção 14.

---

## 1. Identificação do eleitor (a mesa)

**Objetivo do atacante:** votar no lugar de outro, votar duas vezes, ou liberar votos a mais.

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| Me passo por outro eleitor | documento falso, biometria burlada | biometria + documento na **mesa**, que é um aparelho separado e **sem cabo com a urna** | biometria falha e cai pra justificativa manual: brecha conhecida, mitigada por log e limite |
| Mesário libera a urna sem identificar ninguém (voto fantasma) | mesário cúmplice aperta "liberar" | **fichas liberadas e devolvidas, assinadas pela mesa na ata** (papel) × cédulas no mural: sobrou cédula, aparece (golpe 06) | toda a mesa + os fiscais coligados: só pega pelo caderno de assinaturas físico vs comparecimento |
| A máquina de identificar conversa com a urna e entrega "quem votou em quê" | integração indevida | por desenho **não há cabo nem rede** entre mesa e urna; a urna recebe só uma ficha de uso único **sem identidade** | — |

**Por que separar quem-você-é de no-que-você-vota:** se os dois vivem na mesma caixa, quebrar o sigilo é só cruzar dois logs. Separado, nem a urna sabe quem está na cabine. **Mas atenção:** o mural publica as cédulas na ordem em que foram feitas (é a corrente de hashes). Quem anotar a ordem da fila liga cada pessoa à cédula **cifrada** dela: não abre o voto, mas diz qual cifra é de quem (e 3 guardiões juntos, ou um computador quântico no futuro, abririam a dessa pessoa). Por isso a mesa **não guarda ordem nem hora**, só a contagem.

---

## 2. A captura na cabine — o instante da tecla (a etapa mais difícil)

**Objetivo:** a urna mostra A na tela e **registra B**. É o ataque mais sério, porque acontece *antes* de existir qualquer registro pra comparar.

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| Urna trocada por dentro: mostra A, cifra B | firmware malicioso | **desafio de Benaloh**: a urna imprime o código **antes** de saber se o eleitor vai confirmar ou desafiar; quem desafia força a urna a abrir aquela cédula, e um 2º aparelho confere que **é a do código impresso** (golpe 18) e que cifrou o que estava na tela | é **probabilístico**: trocar poucos votos às vezes escapa. Ver a conta na seção 15 |
| Confirmo em casa e a cédula aparece trocada | urna troca **depois** do CONFIRMA | o recibo do eleitor tem que aparecer no mural como **DEPOSITADA** e com a **ficha dele**; apareceu como desafiada = a urna trocou depois do botão (golpe 09, pego pelo `--recibo`) | eleitor que não confere o recibo |
| **Dois eleitores, um recibo** (*clash*, Küsters, Truderung e Vogt, 2012) | a urna dá a dois eleitores que votaram igual o MESMO código e usa a vaga do segundo pra outro voto | a **ficha** sorteada às cegas entra no código: o recibo do segundo aparece com a ficha de outro (golpe 19); a coleta pública de recibos acha código repetido | eleitor que confere sem a ficha |
| **A urna sabe qual cédula é a de verdade** | quem desafia costuma desafiar uma vez e votar em seguida: a urna trapaceia só na cédula logo depois do desafio | o fiscal (que pega ficha como qualquer um) desafia às vezes **duas vezes seguidas** (golpe 21), e o eleitor é orientado a fazer o mesmo de vez em quando | a conta da seção 15 só vale com desafio imprevisível |
| Tela de toque "descalibrada" registra o vizinho | manipulação de UI | tela de confirmação explícita + o desafio pega a divergência tela×cifra | — |
| **Vazar o voto por emanação** (TEMPEST, som, luz, tempo) | antena a metros de distância lê o voto | **hardware**: gaiola de Faraday, sem rádio, conta em tempo constante (HARDWARE.md, peça 1) | ataque de estado-nação com acesso físico muito próximo |
| **Canal subliminar / kleptografia** na aleatoriedade | a urna embute o segredo dentro do "r" aleatório de cada cifra (ou do nonce das provas) | **não resolvido em software**; mitigado por hardware auditado (HARDWARE.md, peças 4 e 5). Aleatoriedade verificável fica pra próxima versão. Só o caso mais grosseiro é recusado: cifra com `r = 0` (voto em claro) | residual real: documentado, mitigado por hardware auditado, não eliminado |

Esta etapa é a razão de existir o HARDWARE.md: **a matemática fecha a contagem; o instante da tecla é com a engenharia física.**

---

## 3. O gerador de aleatoriedade e o tipo de criptografia

**Objetivo:** enfraquecer a cifra na origem, sem ninguém notar. É o ataque mais elegante e o que mais pega "sistema sério" no mundo real.

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| **RNG fraco ou com backdoor** | gerador previsível → dá pra adivinhar o "r" e **decifrar todos os votos** | precedente real: Debian OpenSSL 2008 (32.768 chaves só); Dual_EC_DRBG (backdoor da NSA no padrão). Defesa: **gerador físico + testes de saúde contínuos** (NIST SP 800-90B); se a fonte vicia, a urna **para** (HARDWARE.md, peça 5) | o próprio chip de RNG ser comprometido na fábrica (seção 11) |
| **Troca do tipo de criptografia / downgrade** | o atacante troca a curva/o grupo por um fraco, ou força um algoritmo velho | **não existe negociação em tempo de execução**: o grupo (p, q, g) é **fixo e nasce do hash de uma frase pública**. `python3 grupo.py` refaz e confere. Trocar a cripto = mudar `grupo.py` = **mudar a impressão digital** publicada no README e no PROTOCOLO, que o `grupo.py` confere (e o CI também) e o verificador mostra no passo 1 | — (é justamente o ataque que o parâmetro público mata) |
| **Parâmetro com alçapão** (curva "escolhida a dedo") | números mágicos com estrutura secreta que só o autor conhece | a semente é pública e o processo é determinístico (*nothing-up-my-sleeve*): ninguém escolheu os números, eles **saíram** da frase. Qualquer um reproduz | confiar que a frase-semente não foi garimpada por anos — por isso a frase é banal e pública |
| **Canal subliminar nas provas** (ASA/kleptografia) | a urna escolhe o nonce da prova pra esconder bits do voto | **não resolvido em software**: as provas usam nonce aleatório, como todo Schnorr. O Fiat-Shamir **forte** (o desafio é hash de *tudo*) garante que a prova é **válida**, não que é "limpa": ele resolve o problema do Bernhard-Pereira-Warinschi (2012), não este. Mitigação: hardware auditado. Próxima versão: nonce determinístico (estilo RFC 6979) e aleatoriedade com contribuição externa | **residual real** (seção 14) |

Este é o ponto que separa um brinquedo de uma proposta: **não dá pra "trocar a criptografia" sem trocar um número que está publicado e que qualquer um recalcula.**

---

## 4. Confirmação e recibo

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| Recibo revela o voto → compra de voto | o recibo "prova" em quem votei | o recibo é **hash da cifra** (e da ficha), não o voto; e o eleitor desafia com uma opção **qualquer** (decoy): a cédula que fica pública não é a que conta | o recibo não prova o voto; coerção dentro da cabine fica de fora (seção 14) |
| Recibo falsificado pra acusar o sistema ("defaming") | eleitor inventa um recibo que "sumiu" | o recibo é derivado da cédula e o código bate com as provas; recibo inventado não casa | eleitor mente sobre o que viu na tela: pega-se por contagem de reclamações por urna, não por recibo |
| Ninguém confere o recibo | apatia | **o fiscal de cada partido confere e desafia o dia inteiro** (é dever, não torcida) | se nem os fiscais conferem, a garantia probabilística some |

---

## 5. Armazenamento e **a troca de pendrive**

**Objetivo:** alterar o que a urna gravou, ou impedir que abra.

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| Alterar o arquivo de resultado na mídia | troco bytes no pendrive | o **elo final** (hash encadeado de todas as cédulas) está **impresso na porta** (ata): mudou um bit, o elo não bate (golpes 06, 07). Assinatura do módulo de segurança: proposta de hardware (HARDWARE.md, peça 4), não está no código | — |
| **Trocar o pendrive inteiro** por um meu | substituo a mídia | mesmo assim o conteúdo é cobrado contra a **ata física** (elo final + comparecimento assinado pela mesa): mídia trocada com conteúdo diferente **não casa com a porta** | — pra integridade |
| **Pendrive da chave não abre** | manuseio errado, PIN travado | precedente real: **Basileia, Suíça, mar/2026, 2.048 votos presos**. Defesa: chave **3 de 5 com cópia** — perder uma não para a eleição (HARDWARE.md, peça 12) | é **disponibilidade**, não integridade: no pior caso recomeça da fonte, não muda resultado |

---

## 6. A transmissão — **o sinal** (e o computador infectado no meio)

Esta é a etapa em que quase todo sistema erra, confiando em quem transmite. A resposta daqui é dura:

> **O computador que transmite é tratado como INFECTADO desde o começo. A segurança não depende dele estar limpo.**

Por que isso funciona: o que viaja é o **boletim de cada urna, já lacrado na origem pela corrente de hashes** e com o elo final impresso na porta. O transmissor é um carteiro burro.

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| **Computador da transmissão infectado** altera o boletim no caminho | malware no host de envio/recepção | ele **não tem a chave** pra forjar e **não lê** os votos (cifrados); alterar quebra a corrente/o elo final da porta | — pra integridade (golpes 06 e 07: o elo final da porta não bate) |
| **Interromper o sinal** (cortar, DoS) | derrubo a rede na hora da apuração | é **disponibilidade**: o boletim impresso e publicado na seção é a fonte de verdade; recoleta depois. Precedente real: o painel que "travou em 64% e pulou pra 84%" foi a **vitrine**, não a contagem | atraso e pânico; não muda resultado (o boletim impresso na seção continua valendo) |
| **Reenviar boletins** (replay / duplicar urna) | mando o pacote de uma urna duas vezes | cada urna tem id único na **lista fechada do manifesto**; conta-se **uma vez por urna** (passo 4 do verificador: id único por urna) | — |
| **Injetar uma urna que não existe** | crio uma seção no caminho | não está no manifesto nem na ata (golpe 10) | — |
| MITM troca a cifra por outra válida | intercepta e re-cifra | muda a cédula → quebra a corrente e o elo da porta | — |

**Resumo da etapa:** a rede e o transmissor podem **atrasar ou sumir** com dados (e isso a gente percebe), mas **não conseguem mudar um voto** sem bater de frente com o papel colado na porta.

---

## 7. A contagem / totalização

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| O software que soma conta errado de propósito | totalizador malicioso | a soma é **pública e refeita por qualquer um**: o verificador remultiplica as cifras (soma homomórfica) e confere o anunciado | — |
| Descarta boletins que não gosta | omite seções | lista fechada de urnas (manifesto) + ata por seção: seção faltando aparece (golpe 11) | — |
| Anuncia um resultado que não é o da soma | mente no total | o anunciado tem que **abrir** da soma cifrada, e ser um inteiro entre 0 e o total (golpes 12, 13) | — |

**O ponto:** não importa se o totalizador está infectado. A saída dele é **verificável**, e qualquer um refaz.

---

## 8. A apuração — os guardiões da chave

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| Guardião entrega fatia falsa | parte adulterada | cada fatia tem **prova de conhecimento zero**; a falsa é recusada e os outros abrem sem ele (golpe 14). Se o totalizador publicar a fatia forjada mesmo assim, o verificador recusa. E se o guardião ruim estava no primeiro quórum, os honestos refazem a apuração: pedir a **mesma** soma devolve as mesmas fatias | — |
| Coordenador entrega aos guardiões um mural falso, com uma ata forjada que bate com ele | "abre essa soma aqui pra mim" | **cada guardião confere o mural contra a ata que ELE pegou com os fiscais dele**; a ata que vem junto do pedido não vale (golpe 15) | a ata chegar ao guardião por um caminho que o coordenador não controle (nesta versão, sem assinatura digital da mesa) |
| Transformar o guardião em "máquina de abrir voto" | peço pra abrir uma cédula só, ou a soma sem uma urna, pra achar o voto por diferença | o guardião abre **uma soma na vida** e **calcula a soma ele mesmo**; pedido de **outra** soma é recusado (golpe 15) | — |
| **Chave pirata** na cerimônia | escolho minha parte **em função** das dos outros, pra controlar a chave final | as fatias conferidas barram na cerimônia, e a prova de Schnorr de cada coeficiente deixa qualquer um conferir de fora (golpe 17) | o viés do DKG de Pedersen: quem publica por último pode testar várias partes (seção 11) |
| Conluio pra abrir um voto | 2 guardiões se juntam | precisa de **3 de 5, de lados rivais** (golpe 16) | 3 guardiões rivais coligados: ver seção 15 |
| Número fora do grupo pra vazar o segredo | mando um ponto de ordem pequena | o guardião só abre número **dentro do grupo** (teste `test_guardiao_recusa_numero_de_fora_do_grupo`) | — |

---

## 9. Quem fiscaliza, o quê, por quê, pra quê

A resposta é o coração do projeto.

**QUEM fiscaliza:**
- os **guardiões** (universidade, imprensa, OAB/MP, fiscais de **partidos rivais**) — cada um guarda uma parte da chave;
- os **fiscais na seção** — desafiam a urna (às vezes duas vezes seguidas) e fotografam a ata na porta;
- a **mesa** — assina as fichas liberadas e as devolvidas sem voto (não guarda ordem nem hora);
- e **qualquer cidadão** — baixa o mural, a ata, e roda o `verificador.py` (ou escreve o dele, pelo `PROTOCOLO.md`).

**O QUE cada um checa:**
- o cidadão: todas as provas, a corrente, a soma e o resultado (os 7 passos);
- o fiscal: que o desafio abre a cédula do código impresso, e que o elo da porta é o do mural;
- o eleitor: que o recibo dele está lá, depositado;
- os guardiões: que o mural confere antes de abrir a soma.

**POR QUE funciona (a parte que importa):** a fiscalização **não depende de confiança, depende de desconfiança mútua**. Partido A não confia no B, nem na universidade, nem no TSE — e é exatamente por isso que funciona: pra fraudar sem ser pego, **todos esses inimigos teriam que estar na mesma conspiração E a matemática teria que mentir**. Qualquer um sozinho, honesto, com o verificador na mão, **estoura o esquema**.

**PRA QUÊ:** o objetivo não é impedir todo ataque (impossível). É **detectar**. Uma eleição confiável não é a que ninguém tentou atacar; é a que, se atacada, **mostra**. NASEM 2018: *"melhor cibersegurança não substitui auditoria eficaz."*

**Auditoria por amostra (RLA):** exige um registro em papel de cada voto, que este desenho ainda não tem (o recibo não mostra o voto e a ata não traz votos; e o verificador já confere **todas** as atas, não uma amostra). Se a urna imprimir o voto (proposta futura), a conta da seção 15 diz quantas cédulas de papel sortear.

---

## 10. As cerimônias (gerar a chave, compilar, lacrar)

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| **Compilação não-reproduzível**: o código assinado ≠ o código que eu li | compilador ou ambiente adulterado | **build reproduzível** (Debian/Tor fazem): qualquer um compila e chega no mesmo hash que a urna mostra na tela ao ligar (HARDWARE.md, peça 3) | o compilador ter um trojan histórico (ataque "Trusting Trust"): mitigado por *bootstrap* de compilador |
| Cerimônia de chave teatral | todos os guardiões coligados | guardiões de **lados rivais**; a cerimônia é pública e gravada | colusão total (seção 15) |
| Trocar o binário entre lacrar e votar | acesso físico à urna | lacre que denuncia + o hash na tela no boot + zeroização se abrir (peças 3, 11) | — |

---

## 11. Cadeia de suprimentos e hardware (o andar de baixo)

Esta é, honestamente, a camada **mais difícil** de todas, e nenhum sistema no mundo a resolve 100%.

| Ataque | Como | O que ajuda | Risco que sobra |
|---|---|---|---|
| **Trojan no chip** (fábrica) | lógica maliciosa gravada no silício | dois fornecedores, hardware aberto, inspeção por amostragem (teardown) | **real e grave**: um chip trojan é quase indetectável |
| Implante no teclado/tela | hardware trocado na logística | lacres, amostragem, e a **independência de software**: mesmo uma urna trojanada que mente é pega pelo desafio/recibo **se** tiver gente conferindo | probabilístico, como a seção 2 |
| Firmware do periférico | implante abaixo do SO | módulo de segurança separado + boot medido | — parcial |
| Viés do DKG de Pedersen na chave (Gennaro, Jarecki, Krawczyk e Rabin, 1999) | quem publica por último pode testar várias partes até a chave final ter uma propriedade que ele quer | conhecido; mitigação simples: compromisso por hash antes de revelar; a versão sem viés (GJKR) fica pra próxima | pequeno, documentado |

**A honestidade aqui é a credibilidade:** a gente **não** diz que resolve a cadeia de suprimentos. A gente diz que, mesmo com hardware suspeito, a **independência de software** joga a detecção pro papel e pro desafio — e é por isso que o registro independente (o nosso recibo, o papel da Índia) é inegociável.

---

## 12. Engenharia social e manipulação de pessoas

A maioria dos ataques reais é em **gente**, não em bit.

| Ataque | Como | O que pega | Risco que sobra |
|---|---|---|---|
| **Compra de voto / coerção** | "vota nisso e me prova" | o recibo **não prova** em quem você votou (*receipt-free*); desafio com decoy | alguém do seu lado **dentro** da cabine: a matemática não resolve (é lei + cabine) |
| Subornar/chantagear um **guardião** | grana, ameaça | **3 de 5 de lados rivais**: um vendido não entrega nada (golpe 14) | 3 rivais vendidos ao mesmo tempo (seção 15) |
| Manipular o **mesário/operador/técnico do TSE** | "roda esse programa aqui, confia" | **independência de software**: a maldade dele é pega lá na frente (desafio, recibo, soma pública) | — pra integridade |
| **Phishing / fadiga dos fiscais** | cansar quem fiscaliza, "tá tudo certo, pode ir" | ferramenta de 1 clique (o verificador) e a RLA por amostra reduzem o esforço | fiscal que simplesmente não aparece |
| **Manipular a confiança do público** (o ataque mais barato) | boato de que "foi fraudado" sem prova, ou de que "é impossível conferir" | a resposta é dar **o verificador na mão de todo mundo** — não "confia", **confere** | desinformação é um problema social, não técnico; a gente só dá a ferramenta |

**O recado:** o elo mais fraco é humano — por isso nada no desenho depende de **uma** pessoa honesta. Depende de **inimigos se vigiando** e de **qualquer um poder conferir**.

---

## 13. O eleitor e a cédula

| Ataque | Como | O que pega |
|---|---|---|
| Votar em dois na mesma cédula | enfio dois "1" | prova "soma = 1" (golpe 04) |
| Botar 50 votos numa opção | cifro um número grande | prova "0 ou 1" por opção (golpe 03) |
| Copiar a cédula cifrada de alguém | pra achar o voto pela diferença | provas presas ao id da cédula + cifra repetida barrada (golpe 05) |

---

## 14. O que a gente NÃO resolve (dito na cara)

Credibilidade é isto: um sistema que lista o que **não** faz.

- **Coerção dentro da cabine.** Se tem alguém do seu lado te vigiando, nenhuma matemática ajuda. Isso é lei e cabine fechada.
- **Cadeia de suprimentos / chip trojan.** O andar de baixo (seção 11). Mitigado, não resolvido.
- **Precisa de gente conferindo.** Uma eleição verificável que ninguém verifica não prova nada. Por isso o fiscal desafiador e o recibo conferido com a ficha.
- **A ata não tem assinatura digital.** Ela só protege se chegar ao verificador e a cada guardião pelas fotos dos fiscais, por um caminho que o coordenador da apuração não controla.
- **Urna de contingência.** A urna que quebra no meio do dia ainda não tem saída no protocolo (a reserva não está no manifesto). Próxima versão.
- **A ordem do mural é a ordem da fila** (seção 1): diz qual cifra é de quem, sem abrir o voto.
- **O verificador usa as mesmas peças matemáticas da urna** (`cripto.py`, `guardioes.py`). Verificador independente de verdade é outro programa: por isso o PROTOCOLO.md e os vetores de teste.
- **Colusão total dos adversários.** Se os 3 guardiões rivais, a universidade, a imprensa e o cidadão estiverem **todos** na mesma conspiração, acabou — mas aí já não é mais uma eleição, é um país inteiro mentindo junto.
- **Canal subliminar / kleptografia.** A urna pode tentar vazar o voto pela própria aleatoriedade (seção 2/3). Mitigado por hardware auditado.
- **Futuro quântico.** Um computador quântico grande quebraria o logaritmo discreto e abriria votos **guardados hoje** ("store-now-decrypt-later"). A integridade da eleição de hoje não muda; o sigilo eterno é pesquisa em aberto (migração pós-quântica).
- **Este código é didático.** Não foi auditado por terceiros e o Python vaza tempo (não é tempo-constante). Urna de verdade roda a cripto num chip próprio. **Não use em eleição real.**

---

## 15. As contas que sustentam tudo (números, não opinião)

As contas estão na tabela do README e cabem numa linha de Python: `(1 - d) ** k`.

- **Detecção da urna trapaceira (desafio):** se ela troca `k` votos e cada cédula **com aquele voto** é desafiada com chance `d`, a chance de **nunca** ser pega é `(1−d)^k`. Se quem desafia escolhe a opção ao acaso, `d` cai na proporção (1 ÷ nº de opções) ÷ (fatia do candidato roubado); e a conta supõe desafio imprevisível (seção 2).
  - 100 votos trocados, 10% desafiam → **1 em 37.649** de escapar.
  - 1.000 votos → 1 em 5,7 × 10⁴⁵. Roubar o suficiente pra virar uma eleição **não passa**.
- **Auditoria por amostra (RLA), se houver papel:** risco de 5%, comparação cédula a cédula: margem 10% → ~61 **cédulas**; 2% → ~310; 1% → ~622. Por sondagem (BRAVO), numa disputa de 120 milhões a 50,9% × 49,1% → ~17 mil **cédulas** em média (0,014% dos votos).
- **Conluio dos guardiões:** com 3 de 5, abrir um voto exige **3** dos 5 inimigos juntos; 2 guardiões juntos não sabem nada a mais do que qualquer pessoa da rua: pra abrir, teriam que quebrar a cifra do zero.

---

## Mapa: cada ameaça → onde ela é tratada

| Camada | Arquivo / peça |
|---|---|
| cifra, provas, troca de cripto, Fiat-Shamir | `cripto.py`, `grupo.py` |
| chave dividida, guardião que se defende, chave pirata | `guardioes.py` |
| captura, desafio, recibo, corrente, ata | `urna.py` |
| **transmissão, sinal, host infectado, replay** | elo final + ata (`urna.py`) e passo 4 do `verificador.py` |
| conferência independente (7 passos) | `verificador.py` |
| os 22 golpes rodando | `ataques.py` |
| TEMPEST, pendrive, boot, zeroização, fornecedores | `HARDWARE.md` |
| a especificação pra reescrever o verificador | `PROTOCOLO.md` |

O que tem número de golpe roda: `python3 ataques.py` e `python3 verificador.py`. O resto (hardware, assinaturas, biometria, auditoria por amostra) é proposta de projeto, explicada no HARDWARE.md.
