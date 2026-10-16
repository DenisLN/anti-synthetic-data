"""Confere as fichas das 20 classes contra o código da árvore atual (somente leitura).

Uso (da raiz do repositório, com o Python do projeto):

    python docs-site-plano/verificar-fichas.py [--mostrar] [docs/classes/05-harmonics.md ...]

Sem argumentos confere docs/classes/NN-*.md (20 fichas). Verifica:

1. toda citação ``arquivo.py:A`` ou ``arquivo.py:A-B`` em crase aponta para um arquivo
   existente e para linhas que existem (sem ambiguidade de nome quando o caminho não vem);
2. toda citação ligada a um símbolo, na forma ``Simbolo`` (``arquivo.py:A-B``), bate
   exatamente com o início e o fim do símbolo no ``ast`` (``Classe.metodo``, função ou
   atributo de classe/módulo);
3. as 12 seções do modelo mais "Como o código da classe funciona" existem e a ficha não
   contém "em redação" nem "PREENCHER";
4. cada pendência P-NN que a tabela "Pendências por classe" de docs/projeto/pendencias.md
   atribui à classe aparece na ficha.

``--mostrar`` imprime a primeira linha de cada trecho citado, para conferência a olho.
Código de saída 0 = nada divergente.
"""
import ast
import glob
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTAS = ["logica", "scripts", "experimentos_nativos", "experimentos_waveform", "tests"]

SECOES = [
    "Em uma resposta", "O fenômeno e a norma", "O modelo em `gerar()`", "Como a bancada reproduz",
    "Parâmetros por perfil", "Limites físicos e fator de extremo", "Validação física",
    "As três versões e a correlação esperada", "Quirks e armadilhas", "Histórico por versão",
    "Estado de verificação e pendências", "Como o código da classe funciona", "Referências",
]

_cache_ast = {}
_cache_linhas = {}


def linhas_do(caminho):
    if caminho not in _cache_linhas:
        with open(caminho, encoding="utf-8") as f:
            _cache_linhas[caminho] = f.read().splitlines()
    return _cache_linhas[caminho]


def simbolos(caminho):
    if caminho in _cache_ast:
        return _cache_ast[caminho]
    arvore = ast.parse("\n".join(linhas_do(caminho)))
    achados = {}

    def visita(no, prefixo=""):
        for n in ast.iter_child_nodes(no):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nome = prefixo + n.name
                achados.setdefault(nome, (n.lineno, n.end_lineno))
                if isinstance(n, ast.ClassDef):
                    visita(n, nome + ".")
            elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                alvos = n.targets if isinstance(n, ast.Assign) else [n.target]
                for a in alvos:
                    if isinstance(a, ast.Name):
                        achados.setdefault(prefixo + a.id, (n.lineno, n.end_lineno))

    visita(arvore)
    _cache_ast[caminho] = achados
    return achados


def resolver(arq):
    """Caminho absoluto do arquivo citado, ou (None, motivo)."""
    arq = arq.replace("\\", "/")
    direto = os.path.join(RAIZ, arq)
    if os.path.isfile(direto):
        return direto, None
    candidatos = [os.path.join(RAIZ, p, arq) for p in PASTAS if os.path.isfile(os.path.join(RAIZ, p, arq))]
    if len(candidatos) == 1:
        return candidatos[0], None
    if not candidatos:
        return None, "arquivo não encontrado"
    return None, "nome ambíguo: " + ", ".join(os.path.relpath(c, RAIZ) for c in candidatos)


CIT = re.compile(r"`([\w./\\-]+\.py):(\d+)(?:-(\d+))?`")
SIMB = re.compile(r"`([A-Za-z_][\w.]*)`,? \(?`([\w./\\-]+\.py):(\d+)(?:-(\d+))?`")


def pendencias_por_classe():
    caminho = os.path.join(RAIZ, "docs", "projeto", "pendencias.md")
    resultado = {}
    dentro = False
    with open(caminho, encoding="utf-8") as f:
        for l in f:
            if l.startswith("## 2."):
                dentro = True
                continue
            if dentro and l.startswith("## 3."):
                break
            m = re.match(r"^\| (\d\d) \| (.*) \|\s*$", l)
            if dentro and m:
                resultado[m.group(1)] = sorted(set(re.findall(r"P-\d\d", m.group(2))))
    return resultado


def conferir(ficha, mostrar=False):
    problemas = []
    nome = os.path.basename(ficha)
    cls = nome[:2]
    with open(ficha, encoding="utf-8") as f:
        texto = f.read()

    for m in CIT.finditer(texto):
        arq, a, b = m.group(1), int(m.group(2)), m.group(3)
        b = int(b) if b else a
        caminho, motivo = resolver(arq)
        if caminho is None:
            problemas.append(f"{nome}: `{arq}:{a}`: {motivo}")
            continue
        n = len(linhas_do(caminho))
        if a < 1 or b > n or a > b:
            problemas.append(f"{nome}: `{arq}:{a}-{b}`: fora do arquivo ({n} linhas)")
        elif mostrar:
            print(f"  {arq}:{a}-{b}  {linhas_do(caminho)[a - 1].strip()[:90]}")

    for m in SIMB.finditer(texto):
        simbolo, arq, a, b = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        b = int(b) if b else a
        caminho, motivo = resolver(arq)
        if caminho is None:
            continue
        tabela = simbolos(caminho)
        stem = os.path.splitext(os.path.basename(caminho))[0]
        if simbolo.startswith(stem + "."):
            simbolo = simbolo[len(stem) + 1:]
        if simbolo in tabela:
            alvo = tabela[simbolo]
        else:
            candidatos = [v for k, v in tabela.items() if k.split(".")[-1] == simbolo.split(".")[-1]
                          and (k == simbolo or k.endswith("." + simbolo) or "." not in simbolo)]
            alvo = candidatos[0] if len(candidatos) == 1 else None
            if len(candidatos) > 1 and (a, b) in [tuple(c) for c in candidatos]:
                alvo = (a, b)
        if alvo is None:
            problemas.append(f"{nome}: símbolo `{simbolo}` não existe em {arq}")
        elif tuple(alvo) != (a, b) and not (a == b == alvo[0]):
            problemas.append(f"{nome}: `{simbolo}` está em {arq}:{alvo[0]}-{alvo[1]}, a ficha cita {a}-{b}")

    titulos = re.findall(r"^## (?:\d+\. )?(.+)$", texto, flags=re.M)
    for secao in SECOES:
        if not any(t.strip() == secao for t in titulos):
            problemas.append(f"{nome}: seção ausente: {secao}")
    for proibido in ("em redação", "PREENCHER"):
        if proibido in texto:
            problemas.append(f"{nome}: contém '{proibido}'")

    esperado = pendencias_por_classe().get(cls, [])
    for p in esperado:
        if p not in texto:
            problemas.append(f"{nome}: pendência {p} ausente (consta em projeto/pendencias.md)")
    return problemas


def main(argv):
    mostrar = "--mostrar" in argv
    fichas = [a for a in argv if not a.startswith("--")]
    if not fichas:
        fichas = sorted(glob.glob(os.path.join(RAIZ, "docs", "classes", "[0-2][0-9]-*.md")))
    total = []
    for f in fichas:
        if mostrar:
            print(os.path.basename(f))
        total.extend(conferir(f, mostrar))
    for p in total:
        print("DIVERGE:", p)
    print(f"{len(fichas)} ficha(s) conferida(s); {len(total)} divergência(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
