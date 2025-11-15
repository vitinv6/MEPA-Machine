# 🖥️ Interpretador MEPA — Trabalho 3 de Compiladores

Este repositório contém a implementação completa de um **Interpretador MEPA**, incluindo um **REPL interativo**, suporte à **edição de código MEPA**, execução de programas, depuração passo a passo e gerenciamento de memória/pilha.

Este trabalho corresponde ao **Trabalho 3 da matéria de Compiladores**.

---

## 📌 Funcionalidade Geral

O interpretador oferece um ambiente interativo para:

- Carregar programas MEPA
- Editar linhas de código
- Salvar alterações
- Executar instruções MEPA
- Depurar passo a passo
- Visualizar memória e pilha

A lógica de execução segue exatamente as regras da máquina virtual MEPA.

---

## 🧩 Estruturas Implementadas

### ✔️ **MepaProgram**
- Armazena o programa MEPA na memória
- Manipula inserção, remoção e listagem de linhas
- Gerencia estado de modificação
- Carrega e salva arquivos `.mepa`

### ✔️ **MepaMachine**
- Executa instruções MEPA
- Implementa pilha, memória e saltos
- Mantém tabela de labels
- Oferece modo depuração (DEBUG/NEXT/STOP/STACK)

---

## 📜 Instruções MEPA Suportadas

- **Controle**
  - `INPP`, `PARA`
- **Memória**
  - `AMEM n`, `DMEM n`
  - `CRVL n`, `ARMZ n`
- **Constantes**
  - `CRCT k`
- **Aritméticas**
  - `SOMA`, `SUBT`, `MULT`, `DIVI`, `INVR`
- **Lógicas**
  - `CONJ`, `DISJ`
- **Comparações**
  - `CMME`, `CMMA`, `CMIG`, `CMDG`, `CMEG`, `CMAG`
- **Saltos**
  - `DSVS label/linha`
  - `DSVF label/linha`
- **Diversas**
  - `IMPR`, `NADA`

---

## 💻 Comandos do REPL

Todos os comandos são *case-insensitive*.

| Comando | Descrição |
|--------|-----------|
| `LOAD <arquivo.mepa>` | Carrega um arquivo |
| `LIST` | Lista código (20 linhas por página) |
| `INS <linha> <instr>` | Insere/atualiza uma linha |
| `DEL <linha>` | Remove linha |
| `DEL <linha_i> <linha_f>` | Remove intervalo de linhas |
| `SAVE` | Salva modificações |
| `RUN` | Executa o programa |
| `DEBUG` | Inicia modo de depuração |
| `NEXT` | Executa a próxima instrução (debug) |
| `STOP` | Sai do modo debugger |
| `STACK` | Mostra pilha e memória (debug) |
| `EXIT` | Sai do REPL |

---

## ▶️ Como usar

### **1. Execute o interpretador**
```bash
python MEPA.py
