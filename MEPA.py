#!/usr/bin/env python3
# MEPA.py
#
# Descrição:
# Interpretador/REPL para a linguagem MEPA (Trabalho 3 - Compiladores)
#
# Comandos do REPL (case-insensitive):
#   LOAD <arquivo.mepa>   - carrega arquivo
#   LIST                  - lista código (20 linhas por vez)
#   INS <linha> <instr>   - insere/atualiza linha
#   DEL <linha> [<linha_f>]- remove linha(s)
#   SAVE                  - salva no arquivo aberto
#   RUN                   - executa o programa
#   DEBUG                 - entra no modo depuração (mostra instruções)
#   NEXT                  - executa a próxima instrução (no debug)
#   STOP                  - sai do modo depuração
#   STACK                 - exibe pilha (somente em debug)
#   EXIT                  - finaliza o REPL

import sys
import os
import shlex

# -----------------------
# Estruturas de programa
# -----------------------

class MepaProgram:
    """
    Representa o programa MEPA carregado em memória.
    Mantém um dicionário linha_num -> raw_line_text.
    """
    def __init__(self):
        self.lines = {}  # linha_num (int) -> raw_line_text
        self.modified = False
        self.filename = None

    def set_line(self, lineno: int, raw_text: str):
        self.lines[lineno] = raw_text.strip()
        self.modified = True

    def del_line(self, lineno: int):
        if lineno in self.lines:
            del self.lines[lineno]
            self.modified = True
            return True
        return False

    def del_range(self, li: int, lf: int):
        removed = []
        for n in sorted([ln for ln in self.lines.keys() if li <= ln <= lf]):
            removed.append((n, self.lines[n]))
            del self.lines[n]
        if removed:
            self.modified = True
        return removed

    def get_sorted_lines(self):
        return [(ln, self.lines[ln]) for ln in sorted(self.lines.keys())]

    def clear(self):
        self.lines.clear()
        self.modified = False
        self.filename = None

    def load_from_file(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.readlines()
        self.lines.clear()
        for line in raw:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            # Expect the line to start with line number
            parts = line.strip().split(None, 1)
            try:
                lineno = int(parts[0])
            except Exception:
                # skip invalid lines
                continue
            rest = parts[1] if len(parts) > 1 else ""
            self.lines[lineno] = rest
        self.filename = path
        self.modified = False

    def save_to_file(self, path=None):
        if path is None:
            path = self.filename
        if path is None:
            raise ValueError("Nome de arquivo não especificado.")
        with open(path, 'w', encoding='utf-8') as f:
            for ln, text in self.get_sorted_lines():
                f.write(f"{ln} {text}\n")
        self.filename = path
        self.modified = False

# -----------------------
# Parser de instruções
# -----------------------

def parse_line_text(raw_text: str):
    """
    Parse a raw instruction string into (label, instr, args_list, raw_args_text)
    Examples of raw_text:
      "L1: NADA"
      "CRCT 5"
      "L2: CRVL 1"
    Returns (label_or_None, instr_upper, args_list (strings), raw_args_text)
    """
    text = raw_text.strip()
    label = None
    instr_part = text

    # detect label at start: "L1:" or "L1: INPP"
    if ':' in text:
        before, after = text.split(':', 1)
        tok = before.strip()
        if tok and all(c.isalnum() or c == '_' for c in tok):
            label = tok
            instr_part = after.strip()

    if not instr_part:
        return (label, None, [], "")

    # split instruction and args
    try:
        parts = shlex.split(instr_part)
    except Exception:
        parts = instr_part.split()

    instr = parts[0].upper()
    args = parts[1:]
    raw_args = " ".join(args)
    return (label, instr, args, raw_args)

# -----------------------
# Máquina MEPA (executor)
# -----------------------

class MepaMachine:
    def __init__(self, program: MepaProgram):
        self.program = program
        self.reset_machine_state()

    def reset_machine_state(self):
        self.stack = []
        self.memory = []  # list of int, dynamic with AMEM/DMEM
        self.labels = {}  # label -> lineno
        self.sorted_lines = []  # list of line numbers sorted
        self.line_index_map = {}  # lineno -> index in sorted_lines
        self.pc_index = 0  # index into sorted_lines
        self.debug_mode = False
        self.debug_paused = False
        self.running = False
        self.last_executed_line = None
        self.rebuild_metadata()

    def rebuild_metadata(self):
        """Reconstroi sorted_lines, label table e map de indices."""
        self.sorted_lines = sorted(self.program.lines.keys())
        self.line_index_map = {ln: i for i, ln in enumerate(self.sorted_lines)}
        # build labels table scanning each line's label
        self.labels = {}
        for ln in self.sorted_lines:
            raw = self.program.lines[ln]
            label, instr, args, raw_args = parse_line_text(raw)
            if label:
                self.labels[label] = ln

    def find_pc_for_start(self):
        """Retorna índice do INPP se existir, senão primeiro índice."""
        for i, ln in enumerate(self.sorted_lines):
            raw = self.program.lines[ln]
            _, instr, *_ = parse_line_text(raw)
            if instr == "INPP":
                return i
        return 0 if self.sorted_lines else None

    def get_current_line_lnum(self):
        if 0 <= self.pc_index < len(self.sorted_lines):
            return self.sorted_lines[self.pc_index]
        return None

    def jump_to_line(self, target):
        """
        target can be an integer line number or a label string.
        Returns True on success, False otherwise.
        """
        if isinstance(target, str):
            # try parse as int first
            if target.isdigit() or (target.startswith('-') and target[1:].isdigit()):
                ln = int(target)
                if ln in self.line_index_map:
                    self.pc_index = self.line_index_map[ln]
                    return True
                else:
                    return False
            # try label
            if target in self.labels:
                ln = self.labels[target]
                self.pc_index = self.line_index_map[ln]
                return True
            else:
                return False
        elif isinstance(target, int):
            if target in self.line_index_map:
                self.pc_index = self.line_index_map[target]
                return True
            else:
                return False
        return False

    # ---------- helpers ----------
    def push(self, val):
        try:
            val_i = int(val)
        except:
            if isinstance(val, bool):
                val_i = 1 if val else 0
            else:
                raise ValueError(f"Valor inválido para empilhar: {val}")
        self.stack.append(val_i)

    def pop(self):
        if not self.stack:
            raise RuntimeError("Pilha vazia")
        return self.stack.pop()

    def peek(self):
        if not self.stack:
            raise RuntimeError("Pilha vazia")
        return self.stack[-1]

    def ensure_memory_index(self, idx):
        if idx < 0:
            raise IndexError("Endereço de memória negativo")
        if idx >= len(self.memory):
            raise IndexError(f"Endereço de memória {idx} fora do limite (0..{len(self.memory)-1})")

    # ---------- execução de uma instrução ----------
    def execute_current(self):
        """
        Executa a instrução apontada por pc_index.
        Retorna True se deve continuar (não atingiu PARA), False se encontrou PARA (parar).
        """
        ln = self.get_current_line_lnum()
        if ln is None:
            return False
        raw = self.program.lines[ln]
        label, instr, args, raw_args = parse_line_text(raw)

        # salvar para exibição
        self.last_executed_line = (ln, raw)

        advance_pc = True

        try:
            if instr is None:
                pass
            elif instr == "INPP":
                pass

            elif instr == "AMEM":
                if len(args) != 1:
                    raise RuntimeError("AMEM requer 1 argumento")
                m = int(args[0])
                if m < 0:
                    raise RuntimeError("AMEM argumento inválido")
                self.memory.extend([0]*m)

            elif instr == "DMEM":
                if len(args) != 1:
                    raise RuntimeError("DMEM requer 1 argumento")
                m = int(args[0])
                if m < 0 or m > len(self.memory):
                    raise RuntimeError("DMEM argumento inválido")
                for _ in range(m):
                    self.memory.pop()

            elif instr == "PARA":
                return False

            elif instr == "CRCT":
                if len(args) != 1:
                    raise RuntimeError("CRCT requer 1 argumento")
                self.push(int(args[0]))

            elif instr == "CRVL":
                if len(args) != 1:
                    raise RuntimeError("CRVL requer 1 argumento")
                n = int(args[0])
                self.ensure_memory_index(n)
                val = self.memory[n]
                self.push(val)

            elif instr == "ARMZ":
                if len(args) != 1:
                    raise RuntimeError("ARMZ requer 1 argumento")
                n = int(args[0])
                val = self.pop()
                if n < 0:
                    raise RuntimeError("ARMZ índice negativo")
                if n >= len(self.memory):
                    raise RuntimeError(f"Endereço de memória {n} não alocado")
                self.memory[n] = val

            elif instr == "SOMA":
                b = self.pop()
                a = self.pop()
                self.push(a + b)

            elif instr == "SUBT":
                b = self.pop()
                a = self.pop()
                self.push(a - b)

            elif instr == "MULT":
                b = self.pop()
                a = self.pop()
                self.push(a * b)

            elif instr == "DIVI":
                b = self.pop()
                a = self.pop()
                if b == 0:
                    raise RuntimeError("Divisão por zero")
                self.push(a // b)

            elif instr == "INVR":
                a = self.pop()
                self.push(-a)

            elif instr == "CONJ":
                b = self.pop()
                a = self.pop()
                self.push(1 if (a != 0 and b != 0) else 0)

            elif instr == "DISJ":
                b = self.pop()
                a = self.pop()
                self.push(1 if (a != 0 or b != 0) else 0)

            elif instr == "CMME":
                b = self.pop()
                a = self.pop()
                self.push(1 if a < b else 0)

            elif instr == "CMMA":
                b = self.pop()
                a = self.pop()
                self.push(1 if a > b else 0)

            elif instr == "CMIG":
                b = self.pop()
                a = self.pop()
                self.push(1 if a == b else 0)

            elif instr == "CMDG":
                b = self.pop()
                a = self.pop()
                self.push(1 if a != b else 0)

            elif instr == "CMEG":
                b = self.pop()
                a = self.pop()
                self.push(1 if a <= b else 0)

            elif instr == "CMAG":
                b = self.pop()
                a = self.pop()
                self.push(1 if a >= b else 0)

            elif instr == "DSVS":
                if len(args) != 1:
                    raise RuntimeError("DSVS requer 1 argumento")
                target = args[0]
                if not self.jump_to_line(target):
                    raise RuntimeError(f"DSVS: label/linha {target} não encontrado")
                return True

            elif instr == "DSVF":
                if len(args) != 1:
                    raise RuntimeError("DSVF requer 1 argumento")
                cond = self.pop()
                if cond == 0:
                    target = args[0]
                    if not self.jump_to_line(target):
                        raise RuntimeError(f"DSVF: label/linha {target} não encontrado")
                    return True

            elif instr == "NADA":
                pass

            elif instr == "IMPR":
                val = self.peek()
                print(val)

            else:
                raise RuntimeError(f"Instrução desconhecida: {instr}")

            self.pc_index += 1
            return True
        except Exception as e:
            raise RuntimeError(f"Erro na linha {ln}: {str(e)}")

    def run(self):
        """Executa o programa inteiro."""
        self.reset_machine_state()
        start_idx = self.find_pc_for_start()
        if start_idx is None:
            raise RuntimeError("Nenhum código para executar")
        self.pc_index = start_idx
        self.running = True
        try:
            while self.running and self.pc_index < len(self.sorted_lines):
                continue_exec = self.execute_current()
                if not continue_exec:
                    break
        finally:
            self.running = False

    def debug_start(self):
        """Inicia modo debug."""
        self.reset_machine_state()
        start_idx = self.find_pc_for_start()
        if start_idx is None:
            raise RuntimeError("Nenhum código para executar")
        self.pc_index = start_idx
        self.debug_mode = True
        self.running = True
        # Exibe primeira instrução
        ln = self.get_current_line_lnum()
        if ln is not None:
            raw = self.program.lines[ln]
            print(f"{ln} {raw}")

    def debug_next(self):
        """Executa próxima instrução no modo debug."""
        if not self.debug_mode or not self.running:
            raise RuntimeError("Não está em modo debug")
        
        if self.pc_index >= len(self.sorted_lines):
            print("Programa finalizado")
            self.debug_mode = False
            self.running = False
            return

        continue_exec = self.execute_current()
        
        if not continue_exec:
            print("Programa finalizado (PARA)")
            self.debug_mode = False
            self.running = False
            return

        # Mostra próxima instrução
        if self.pc_index < len(self.sorted_lines):
            ln = self.get_current_line_lnum()
            if ln is not None:
                raw = self.program.lines[ln]
                print(f"{ln} {raw}")
        else:
            print("Programa finalizado")
            self.debug_mode = False
            self.running = False

    def debug_stop(self):
        """Para o modo debug."""
        self.debug_mode = False
        self.running = False
        print("Modo de depuração encerrado")

    def show_stack(self):
        """Exibe conteúdo da memória e pilha."""
        if not self.debug_mode:
            print("Comando STACK disponível apenas em modo de depuração")
            return
        
        if not self.memory and not self.stack:
            print("Pilha vazia")
            return
        
        print("Conteúdo da pilha")
        # Mostra memória
        for i, val in enumerate(self.memory):
            print(f"{i}: {val}")
        # Mostra stack adicional (além da memória)
        stack_start = len(self.memory)
        for i, val in enumerate(self.stack):
            print(f"{stack_start + i}: {val}")

# -----------------------
# REPL
# -----------------------

def repl():
    """Loop principal do REPL."""
    program = MepaProgram()
    machine = MepaMachine(program)
    
    print("Interpretador MEPA - Digite 'EXIT' para sair")
    
    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue
            
            parts = user_input.split(None, 1)
            cmd = parts[0].upper()
            args_text = parts[1] if len(parts) > 1 else ""
            
            # Comandos que podem interromper DEBUG
            if cmd in ["LOAD", "RUN", "INS", "DEL", "EXIT"] and machine.debug_mode:
                machine.debug_stop()
            
            if cmd == "EXIT":
                if program.modified:
                    resp = input("Há alterações não salvas. Deseja salvar antes de sair? (s/n): ").strip().lower()
                    if resp == 's':
                        try:
                            program.save_to_file()
                            print(f"Arquivo '{program.filename}' salvo com sucesso")
                        except Exception as e:
                            print(f"Erro ao salvar: {e}")
                print("Encerrando...")
                break
            
            elif cmd == "LOAD":
                if not args_text:
                    print("Erro: especifique o nome do arquivo")
                    continue
                
                filename = args_text.strip()
                
                if program.modified:
                    resp = input("Há alterações não salvas. Deseja salvar antes de carregar outro arquivo? (s/n): ").strip().lower()
                    if resp == 's':
                        try:
                            program.save_to_file()
                            print(f"Arquivo '{program.filename}' salvo com sucesso")
                        except Exception as e:
                            print(f"Erro ao salvar: {e}")
                
                try:
                    program.load_from_file(filename)
                    machine.rebuild_metadata()
                    print(f"Arquivo '{filename}' carregado com sucesso.")
                except FileNotFoundError:
                    print(f"Erro: arquivo '{filename}' não encontrado")
                except Exception as e:
                    print(f"Erro ao carregar arquivo: {e}")
            
            elif cmd == "LIST":
                lines = program.get_sorted_lines()
                if not lines:
                    print("Nenhum código na memória")
                    continue
                
                page_size = 20
                for i in range(0, len(lines), page_size):
                    page = lines[i:i+page_size]
                    for ln, text in page:
                        print(f"{ln} {text}")
                    
                    if i + page_size < len(lines):
                        input("Pressione alguma tecla para continuar.")
            
            elif cmd == "INS":
                if not args_text:
                    print("Erro: INS requer <LINHA> <INSTRUÇÃO>")
                    continue
                
                parts = args_text.split(None, 1)
                if len(parts) < 2:
                    print("Erro: INS requer <LINHA> <INSTRUÇÃO>")
                    continue
                
                try:
                    lineno = int(parts[0])
                    if lineno < 0:
                        print("Erro: número de linha não pode ser negativo")
                        continue
                    
                    instr_text = parts[1]
                    
                    if lineno in program.lines:
                        program.set_line(lineno, instr_text)
                        print(f"Linha atualizada:")
                        print(f"{lineno} {instr_text}")
                    else:
                        program.set_line(lineno, instr_text)
                        print(f"Linha inserida:")
                        print(f"{lineno} {instr_text}")
                    
                    machine.rebuild_metadata()
                
                except ValueError:
                    print("Erro: número de linha inválido")
            
            elif cmd == "DEL":
                if not args_text:
                    print("Erro: DEL requer <LINHA> ou <LINHA_I> <LINHA_F>")
                    continue
                
                parts = args_text.split()
                
                if len(parts) == 1:
                    try:
                        lineno = int(parts[0])
                        if program.del_line(lineno):
                            print(f"Linha removida:")
                            print(f"{lineno}")
                            machine.rebuild_metadata()
                        else:
                            print(f"Erro: Linha {lineno} inexistente")
                    except ValueError:
                        print("Erro: número de linha inválido")
                
                elif len(parts) == 2:
                    try:
                        li = int(parts[0])
                        lf = int(parts[1])
                        
                        if li > lf:
                            print("Erro: intervalo inválido (linha inicial > linha final)")
                            continue
                        
                        removed = program.del_range(li, lf)
                        if removed:
                            print(f"Linhas removidas:")
                            for ln, text in removed:
                                print(f"{ln} {text}")
                            machine.rebuild_metadata()
                        else:
                            print(f"Nenhuma linha encontrada no intervalo {li}-{lf}")
                    
                    except ValueError:
                        print("Erro: números de linha inválidos")
                else:
                    print("Erro: DEL requer <LINHA> ou <LINHA_I> <LINHA_F>")
            
            elif cmd == "SAVE":
                if not program.lines:
                    print("Erro: nenhum código na memória para salvar")
                    continue
                
                try:
                    program.save_to_file()
                    print(f"Arquivo '{program.filename}' salvo com sucesso")
                except Exception as e:
                    print(f"Erro ao salvar arquivo: {e}")
            
            elif cmd == "RUN":
                if not program.lines:
                    print("Erro: nenhum código na memória")
                    continue
                
                try:
                    machine.run()
                except Exception as e:
                    print(f"Erro na execução: {e}")
            
            elif cmd == "DEBUG":
                if not program.lines:
                    print("Erro: nenhum código na memória")
                    continue
                
                try:
                    print("Iniciando modo de depuração:")
                    machine.debug_start()
                except Exception as e:
                    print(f"Erro: {e}")
            
            elif cmd == "NEXT":
                if not machine.debug_mode:
                    print("Erro: não está em modo de depuração. Use DEBUG primeiro")
                    continue
                
                try:
                    machine.debug_next()
                except Exception as e:
                    print(f"Erro: {e}")
            
            elif cmd == "STOP":
                if not machine.debug_mode:
                    print("Não está em modo de depuração")
                    continue
                
                machine.debug_stop()
            
            elif cmd == "STACK":
                machine.show_stack()
            
            else:
                print(f"Erro: comando inválido")
        
        except KeyboardInterrupt:
            print("\nUse EXIT para sair")
        except EOFError:
            print("\nEncerrando...")
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    repl()
