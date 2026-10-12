# Protocolo da Urna do Garoto; (v2)

Especificação para quem quiser escrever **o seu próprio verificador**, em qualquer linguagem, sem ler o meu código.
Se o seu verificador e o meu disserem OK para o mesmo mural, você não precisa confiar em nenhum dos dois.
No fim tem **vetores de teste**: se o seu código bate com eles, o seu hash é o mesmo que o meu.

Notação: `^` é potência mod `p`, contas de expoente são mod `q`, `x⁻¹` é o inverso mod `p`, e `‖` separa os itens de uma lista.

O que mudou da v1 pra v2 (auditoria de 12/10/2026, antes de publicar): a **ficha** entra no código da cédula, a sessão sem voto (**SEM_VOTO**) entra na corrente, a mesa conta as **fichas devolvidas**, o recibo tem **32 dígitos**, o desafio é conferido **na cabine** contra o código impresso, e o guardião usa **a ata dele**.

---

## 1. O grupo

- `p`: primo de 3072 bits. `q`: primo de 256 bits com `q | p − 1`. `g`: gerador do subgrupo de ordem `q` (`g^q = 1` e `g ≠ 1`).
- Os três saem da semente `"Garoto do Programa; Urna do Garoto; grupo v1"` com `gerar_grupo()` (`grupo.py`). Em todos os passos, `SHAKE256(texto, n bits)` é o SHAKE-256 do texto em UTF-8, com `n/8` bytes de saída lidos como inteiro **big-endian**, e `i` (ou `0`) vai em decimal ASCII, sem zero à esquerda:
  - `q` = o primeiro `SHAKE256("semente|q|i", 256)`, com o bit mais alto e o mais baixo ligados, que for primo, com `i = 0, 1, 2…` (dá `i = 79`);
  - `k0 = (SHAKE256("semente|p|0", 3072)`, com o bit mais alto ligado`) // q`, arredondado **pra cima** pra par (`k0 + k0 mod 2`). `p` = o primeiro `k·q + 1` primo, com `k = k0, k0+2, k0+4…` (dá `k = k0 + 2·1005`);
  - `g = h^((p−1)/q)` com `h = 2 + SHAKE256("semente|g|i", 3072) mod (p − 3)`, o primeiro `i` que der `g ≠ 1` (dá `i = 0`).
- **Impressão digital** (SHA-256 de `p`, `q` e `g`, cada um em 384 bytes big-endian): `122c6a8920fbbee3fde975fb2194b84c2672dfd482a855daa7ce998a28250e8f`. `python3 grupo.py` refaz tudo e confere.
- **Pertinência:** todo elemento que vem do mural precisa ter `0 < x < p` e `x^q = 1`. Todo expoente precisa ter `0 ≤ e < q`. Quem não passar é recusado **antes** de qualquer conta.

## 2. Codificação e hash

`cod(x)` é injetiva:
| tipo | bytes |
|---|---|
| inteiro `n ≥ 0` | `"I"` + tamanho em bytes (4 bytes, big-endian) + `n` em big-endian mínimo (`0` vira `00`) |
| texto | `"S"` + tamanho **em bytes UTF-8** (não em caracteres: "Pão de queijo" tem 14) + UTF-8 |
| bytes | `"B"` + tamanho + bytes |
| lista/tupla | `"L"` + quantidade de itens (4 bytes) + `cod(item)` de cada item, em ordem |

Booleanos e negativos são proibidos.

- `H(rótulo, a, b, …) = SHA-256(cod(["urna-do-garoto/v2", rótulo, [a, b, …]]))`, em hexadecimal minúsculo.
- `Hq(rótulo, a, b, …) = int(SHA-512(cod(["urna-do-garoto/v2", rótulo, [a, b, …]])), big-endian) mod q`.

## 3. Receitas

| nome | receita |
|---|---|
| pré-contexto | `H("pre-contexto", p, q, g, eleicao, [opções], [guardiões], quorum, [urnas])` |
| contexto `ctx` | `H("contexto", pré, [[nº, nome, [C₀…Cₖ₋₁]] de cada guardião])` |
| código inicial da urna | `H("inicio", ctx, nome_da_urna)` |
| código da cédula | `H("codigo", ctx, anterior, id, ficha, [[α,β] de cada opção], [[c₀,c₁,v₀,v₁] de cada opção], [c,v] da soma)` |
| código da sessão sem voto | `H("sem-voto", ctx, anterior, id, ficha)` |
| elo | `H("elo", ctx, código, estado)` com estado `"DEPOSITADA"`, `"DESAFIADA"` ou `"SEM_VOTO"` |
| fechamento | `H("fechamento", ctx, nome_da_urna, último_elo, nº_de_depositadas, nº_de_sem_voto)` |
| lacre | `H("lacre", json)`: o mural sem a chave `"lacre"`, serializado como o `json.dumps(…, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` do Python: chaves em ordem de ponto de código Unicode, sem espaços, UTF-8 cru, e só `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f` e `\u00XX` (controles) escapados |

O `id` da n-ésima entrada da urna `U` (contando desafiadas e sessões sem voto) é `U/` + `n` com **pelo menos** 6 dígitos (ex.: `secao-001/000007`).
A primeira entrada tem `anterior = código inicial`, e cada entrada seguinte tem `anterior = elo da entrada de antes`.

**A ficha** são 16 dígitos hexadecimais minúsculos (64 bits). O eleitor sorteia às cegas um cartão de um saco embaralhado na mesa (a mesa não anota quem pegou qual) e digita na urna: é isso que libera a cabine. O fiscal que testa a urna pega ficha do mesmo saco, pra urna não saber quem é. **Sessão** é tudo que a urna faz com uma ficha: zero ou mais cédulas DESAFIADAS e **um** fim, que é uma cédula DEPOSITADA ou uma entrada SEM_VOTO (o mesário apertou ENCERRAR: o eleitor desistiu, ou era teste de fiscal). Cédula que ninguém confirmou nunca conta: se a sessão acaba com uma cédula esperando, ela é aberta como DESAFIADA antes do SEM_VOTO.

## 4. Cifra e provas

**Cifra (ElGamal exponencial):** `(α, β) = (g^r, g^m · K^r)`, com `K` a chave da eleição e `r` aleatório. O produto das cifras soma os `m`. Cifra de cédula com `α = 1` (`r = 0`, o voto ficaria em claro) é recusada.

**Schnorr** (o guardião conhece `x` com `X = g^x`): `a = g^u`, `c = Hq("conhecimento", ctxₚ, X, a)`, `v = u + c·x`.
Para conferir, recalcula `a = g^v · X^(−c)` e checa `c`.
Para o coeficiente `t` do guardião `i`: `ctxₚ = [pré, "coeficiente", i, t]`.

**Chaum-Pedersen** (`log_g1 h1 = log_g2 h2 = x`): `a = g1^u`, `b = g2^u`, `c = Hq(rótulo, ctxₚ, g1, h1, g2, h2, a, b)`, `v = u + c·x`.
Para conferir, recalcula `a = g1^v · h1^(−c)` e `b = g2^v · h2^(−c)` e checa `c`.
- **soma da cédula = 1:** rótulo `"soma"`, `ctxₚ = [ctx, id]`, `g1 = g`, `h1 = Πα`, `g2 = K`, `h2 = Πβ · g⁻¹`;
- **fatia de apuração do guardião j, opção i:** rótulo `"decifra"`, `ctxₚ = [ctx, "apuracao", i]`, `g1 = g`, `h1 = Kⱼ`, `g2 = A`, `h2 = Mⱼ`.

**0 ou 1 (disjuntiva de Cramer-Damgård-Schoenmakers)** para a opção `i` da cédula `id`, com `ctxₚ = [ctx, id, i]`:
- para `j ∈ {0, 1}`: `aⱼ = g^vⱼ · α^(−cⱼ)` e `bⱼ = K^vⱼ · (β · g^(−j))^(−cⱼ)`;
- aceita se `c₀ + c₁ ≡ Hq("zero-ou-um", ctxₚ, K, α, β, a₀, b₀, a₁, b₁)` e `α ≠ 1`.

**Guardiões (DKG de Pedersen, com o segredo verificável de Feldman):**
- o guardião `i` publica `Cᵢₜ = g^aᵢₜ`, com `t = 0…k−1`;
- a chave da eleição é `K = Π Cᵢ₀`;
- a chave de verificação do guardião `j` é `Kⱼ = Πᵢ Πₜ Cᵢₜ^(jᵗ mod q)`;
- na apuração, com os presentes `S` (pelo menos `k`):
  - os pesos de Lagrange são `wⱼ = Π_{l∈S, l≠j} l · (l − j)⁻¹ mod q`;
  - `A^s = Π Mⱼ^wⱼ`;
  - `g^votos = B · (A^s)⁻¹`, com `(A, B)` a soma cifrada da opção.

## 5. O mural (JSON)

Os números vão em hexadecimal **canônico**: minúsculo, sem `0x` e sem zero à esquerda (o zero é `"0"`). Contagens são inteiros JSON (`true` não vale 1).
Cada objeto tem **exatamente** os campos abaixo: campo a mais (um `cpf` escondido na cédula, por exemplo) torna o mural inválido. JSON com **chave repetida** também é inválido (quem lê de olho veria um valor e o programa conferiria outro).
O `resultado` vem na mesma ordem das `opcoes` do manifesto. O `quorum` vai de 2 até o número de guardiões (com quórum 1, cada guardião abriria tudo sozinho).

```
{
 "versao": "urna-do-garoto/v2",
 "grupo": {"p", "q", "g"},
 "manifesto": {"eleicao", "opcoes": [..], "guardioes": [..], "quorum", "urnas": [..]},
 "cerimonia": [{"numero", "nome", "coeficientes": [Cᵢ₀..], "provas": [[c, v]..]}],
 "chave": K,
 "contexto": ctx,
 "urnas": {"<nome>": {"comparecimento", "devolvidas", "depositadas", "sem_voto", "elo_final", "fechamento"}},
 "cedulas": [{"id", "urna", "anterior", "ficha", "codigo", "cifras": [[α, β]..], "provas": [[c₀, c₁, v₀, v₁]..],
              "prova_soma": [c, v], "estado", "abertura": null | {"escolha", "segredos": [r..]}}
             | {"id", "urna", "anterior", "ficha", "codigo", "estado": "SEM_VOTO"}],
 "apuracao": {"totais": [[A, B]..], "fatias": [{"guardiao", "por_opcao": [[M, c, v]..]}],
              "recusados": [..], "resultado": {"<opção>": votos}},
 "lacre": hash
}
```

`comparecimento` e `devolvidas` são da **mesa** (fichas liberadas e fichas que voltaram sem voto); `depositadas`, `sem_voto`, `elo_final` e `fechamento` são da **urna**.
A lista de `urnas` é fechada e publicada **antes** da eleição, no manifesto, junto com o `contexto`: anota o `contexto` num lugar que você confia e passa `--contexto` pro verificador.

### A ata (fica FORA do mural)

Quem monta o mural não pode ser a única fonte das contas nem do elo final. Por isso cada seção produz uma **ata**:
- o que a urna imprime e é colado na porta: `elo_final`, `depositadas`, `sem_voto`;
- o que a mesa (outro aparelho) assina: `comparecimento` (fichas liberadas) e `devolvidas` (fichas que voltaram sem voto).

Os fiscais fotografam a ata, que é publicada em separado:

```
{"versao": "urna-do-garoto/v2", "contexto": ctx,
 "urnas": {"<nome>": {"comparecimento", "devolvidas", "depositadas", "sem_voto", "elo_final"}}}
```

**A ata não tem assinatura digital nesta versão.** Ela só vale como prova se veio das fotos das portas, e não do mesmo lugar que o mural. Quem só fotografou algumas seções confere essas com `--ata-parcial`.

## 6. Os 7 passos da verificação

1. **Grupo:** é o do `grupo.py` (impressão digital acima), e `p` e `q` são primos. Com `--paranoico`, refaz da semente.
2. **Cerimônia:**
   - os guardiões têm números `1…n`, na ordem e com os nomes do manifesto;
   - todas as provas de Schnorr dos coeficientes conferem;
   - `K = Π Cᵢ₀`, com `K ≠ 1` e `K` no grupo;
   - o contexto bate (e, com `--contexto`, é o publicado antes da eleição).
3. **Cédulas:**
   - em cada cédula, as cifras estão no grupo e nenhuma tem `α = 1`;
   - a prova 0-ou-1 de cada opção confere;
   - a prova de soma = 1 confere;
   - o código bate (e o da sessão sem voto também);
   - nenhum `α` se repete no mural inteiro (proteção contra cópia de cédula).
4. **Urnas e corrente:**
   - as urnas do mural são **exatamente** as do manifesto (nem fantasma, nem sumida);
   - por urna, os ids são sequenciais e cada `anterior` é o elo da entrada de antes;
   - **as sessões:** cada ficha aparece numa sessão só (desafiadas seguidas de **um** fim, DEPOSITADA ou SEM_VOTO), e nenhuma sessão fica sem fim;
   - o elo final e o fechamento batem;
   - `depositadas no mural = depositadas declaradas = comparecimento − devolvidas` e `sem_voto no mural = sem_voto declaradas = devolvidas`;
   - **com a ata:** o elo final recalculado é o da porta; as `depositadas` e `sem_voto` da porta são as do mural; `comparecimento − devolvidas` da mesa é o número de depositadas; e `devolvidas` é o número de SEM_VOTO. Toda urna do manifesto precisa ter ata (com `--ata-parcial`, as que faltam viram aviso e o resultado sai com código 2), e a ata não pode trazer urna fora do manifesto;
   - **sem a ata,** a matemática pode até conferir, mas cédula enfiada com as contas reescritas dentro do mural passaria. Por isso o verificador **não** diz "tudo confere" sem a ata (sai com código 2).
5. **Desafiadas:**
   - os segredos refazem exatamente as cifras, com 1 na `escolha` e 0 no resto;
   - cédula depositada não pode ter `abertura`.
6. **Soma:** os `totais` são o produto das cifras das depositadas.
7. **Apuração:**
   - pelo menos `k` guardiões diferentes;
   - todas as fatias têm prova válida contra `Kⱼ`;
   - cada número anunciado é um inteiro entre 0 e o total de depositadas. Isso é obrigatório: como `g^q = 1`, somar `q` numa opção e tirar `q` de outra passaria na conta do expoente;
   - `g^(votos anunciados) = B · (A^s)⁻¹` em cada opção;
   - os votos somam o número de depositadas;
   - `recusados` só pode ter nomes do manifesto, sem repetir, que não estão entre os presentes. É **informativo**: sem assinatura dos guardiões, o verificador não tem como provar quem entregou a fatia falsa.

E por último: o lacre bate. O lacre é um hash sem chave, então só vale como âncora se for anotado fora do mural (por exemplo, publicado na hora).

## 7. O desafio e o recibo

O recibo leva os **32** primeiros dígitos hexadecimais do código (128 bits), em 8 grupos de 4. O QR code leva o código inteiro (64 dígitos). O verificador só aceita o recibo inteiro (32 dígitos) ou o QR code. Por que 32: quem escolhe a cédula é a urna, então ela pode procurar **duas** cédulas com o mesmo começo de código (uma honesta pro desafio e uma trocada pro mural). Isso custa ~2^(bits/2): com 128 bits, 2^64.

- **Na cabine, quem desafiou:** o app lê o QR (o código inteiro) **antes** de apertar DESAFIA. Depois recebe a cédula aberta (`id, anterior, ficha, cifras, provas, prova_soma, abertura`) e confere: (1) as provas; (2) o código recalculado é **o do QR**; (3) a ficha é a sua; (4) os segredos refazem as cifras; (5) a opção é a da tela. Sem o (2), a urna troca a cédula na hora do desafio e abre uma honesta.
- **Em casa, recibo só vale contra mural que confere.** Num mural forjado, qualquer recibo pode "aparecer". Por isso o `--recibo` confere o mural inteiro primeiro (passos 1 a 7, com a ata se tiver) e depois confere de novo a cédula do recibo: provas e código.
- **Eu confirmei:** o código tem que estar no mural **como DEPOSITADA** e **com a minha ficha** (`--ficha`). Se estiver como DESAFIADA, a urna trocou a cédula depois do botão. Se estiver com a ficha de outro, a urna te deu o recibo de **outro eleitor** que votou igual e trocou o teu voto (ataque de *clash*, Küsters, Truderung e Vogt, 2012). Se o código não estiver e a tua ficha aparecer como SEM_VOTO, a urna jogou teu voto fora.
- **Eu desafiei:** o código tem que estar como DESAFIADA, e os segredos refazem as cifras. O app mostra a opção que a urna tinha cifrado, e ela tem que ser a que estava na tela.
- **Desafie com qualquer opção.** A cédula desafiada fica pública, então não precisa ser o seu voto. E **de vez em quando desafie de novo**: a urna sabe que a cédula logo depois de um desafio costuma ser o voto de verdade.
- **Coleta pública de recibos** (`--recibos arquivo`): o mesmo código na mão de dois eleitores é prova de clash.

## 8. As regras do guardião

Quem decide abrir é o guardião, e ele não confia em quem pediu:
1. **Sem a ata das portas, não abre. E a ata é a dele:** a que os fiscais dele montaram (ou conferiram, seção por seção) com as fotos das portas, **antes** de qualquer pedido. Nunca a que vem junto com o pedido: quem monta um mural sob medida monta uma ata que bate com ele.
2. **Confere o mural sozinho:** passos 1 a 5, com a ata dele. Mural que não confere, ele não abre.
3. **Confere que a cerimônia é a dele:** os compromissos dele estão no mural, iguaizinhos.
4. **Calcula a soma ele mesmo**, multiplicando as cédulas depositadas. Ninguém entrega "a soma" pronta pra ele.
5. **Abre UMA soma na vida.** Pedido repetido da **mesma** soma recebe as mesmas fatias (não vaza nada novo, e uma apuração que falhou por culpa de outro guardião pode ser refeita). Qualquer **outra** soma (sem uma urna, só com uma cédula…) é recusada: é tentativa de descobrir voto por diferença. Na vida real, isso é estado guardado, não memória.
6. **Só faz conta com número de dentro do grupo.** Fora dele, a resposta vazaria pedaços do segredo pelo subgrupo pequeno.

## 9. Vetores de teste

Com o domínio `"urna-do-garoto/v2"` (os mesmos de `test_cripto.py`):

| entrada | saída (hexadecimal) |
|---|---|
| `cod(0)` | `490000000100` |
| `cod(256)` | `49000000020100` |
| `cod("Pão")` | `530000000450c3a36f` |
| `cod([1, "a"])` | `4c00000002490000000101530000000161` |
| `H("inicio", "0"×64, "secao-001")` | `1203ed2df92b429479ac04b9e2824b8923f4eafd2029420d16b297b2d2be69ff` |
| `H("elo", "0"×64, "ab", "DEPOSITADA")` | `846d517ef26fe00927efd8e635d4ce306fe96c6269691fc0e8e97bbab22a855c` |
| `Hq("soma", ["0"×64, "secao-001/000001"], 2, 3)` | `ca33ea2a96bae2032ee7e8b09a0a2c30754cbb5b470062f1bcee84cfb2c5541e` |
| impressão digital do grupo | `122c6a8920fbbee3fde975fb2194b84c2672dfd482a855daa7ce998a28250e8f` |

Pra testar o seu verificador de ponta a ponta: `python3 eleicao.py` gera um mural e uma ata honestos, e cada golpe do `ataques.py` é um mural (ou uma situação) que o seu verificador tem que recusar.
