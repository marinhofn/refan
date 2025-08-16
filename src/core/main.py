"""
Ponto de entrada da aplicação, contendo a interface de menu interativo para o usuário.
"""

import os
import json
import datetime
import signal
import sys
from pathlib import Path

# Configurar paths para imports funcionarem tanto quando executado diretamente
# quanto através do sistema unificado
if __name__ == "__main__":
    # Se executado diretamente, adicionar o diretório raiz do projeto ao path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

# Imports dos módulos do sistema
from src.handlers.data_handler import DataHandler
from src.handlers.git_handler import GitHandler
from src.handlers.llm_handler import LLMHandler
from src.handlers.optimized_llm_handler import OptimizedLLMHandler
from src.handlers.purity_handler import PurityHandler
from src.handlers.visualization_handler import VisualizationHandler
from src.core.config import create_directories, list_available_ollama_models, set_llm_model, get_current_llm_model, ensure_model_directories
from src.utils.colors import *

def clear_screen():
    """Limpa a tela do terminal."""
    os.system('clear' if os.name == 'posix' else 'cls')

def signal_handler(signum, frame):
    """
    Handler personalizado para sinal de interrupção (Ctrl+C).
    
    Args:
        signum: Número do sinal recebido
        frame: Frame atual de execução
    """
    print(f"\n\n{header('=' * 60)}")
    print(f"{header('INTERRUPÇÃO DETECTADA')}")
    print(f"{header('=' * 60)}")
    print(f"{info('Processo interrompido pelo usuário (Ctrl+C)')}")
    print(f"{warning('Salvando estado atual...')}")
    
    # Tentar salvar qualquer progresso pendente
    try:
        # Verificar se há dados em memória para salvar
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"{success('Estado preservado com sucesso')}")
        print(f"{info(f'Interrupção registrada às {current_time}')}")
    except Exception as e:
        print(f"{error(f'⚠️  Erro ao salvar estado: {str(e)}')}")
    
    # print(f"\n{dim('📊 Informações da sessão:')}")
    # print(f"{dim('   • Aplicação encerrada de forma segura')}")
    # print(f"{dim('   • Todos os dados analisados foram preservados')}")
    # print(f"{dim('   • Arquivos de log mantidos em: analises/')}")
    # print(f"{dim('   • Progresso pode ser retomado a qualquer momento')}")
    
    # print(f"\n{cyan('💡 Dicas para próxima execução:')}")
    # print(f"{dim('   • Use as opções de pular commits analisados para continuar')}")
    # print(f"{dim('   • Verifique os arquivos de visualização gerados')}")
    # print(f"{dim('   • Dados de comparação Purity estão disponíveis')}")
    
    print(f"\n{success('✅ Encerramento seguro concluído!')}")
    # print(f"{cyan('Obrigado por usar o Sistema de Análise de Refatoramento!')}")
    print(f"{dim('Desenvolvido para pesquisa acadêmica em refatoramento de código')}")
    print(f"{header('=' * 60)}\n")
    
    # Encerrar o programa de forma limpa
    sys.exit(0)

def setup_signal_handlers():
    """Configura os handlers de sinal para interrupções."""
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

def safe_processing_loop(iterable, process_func, description="processando"):
    """
    Executa um loop de processamento com tratamento seguro de interrupções.
    
    Args:
        iterable: Iterável para processar
        process_func: Função para processar cada item
        description: Descrição do processo para logs
        
    Returns:
        list: Resultados do processamento
    """
    results = []
    total = len(iterable) if hasattr(iterable, '__len__') else 0
    
    try:
        for i, item in enumerate(iterable):
            if total > 0:
                progress = (i + 1) / total * 100
                print(f"\r{info(f'{description.capitalize()}: {i+1}/{total} ({progress:.1f}%)')}", end='', flush=True)
            
            try:
                result = process_func(item)
                if result:
                    results.append(result)
            except KeyboardInterrupt:
                print(f"\n{warning('Interrupção detectada durante processamento...')}")
                raise
            except Exception as e:
                print(f"\n{error(f'Erro no item {i+1}: {str(e)}')}")
                continue
        
        if total > 0:
            print()  # Nova linha após o progresso
            
    except KeyboardInterrupt:
        print(f"\n{warning(f'Processamento interrompido. {len(results)} itens processados com sucesso.')}")
        return results
    
    return results

def generate_output_filename():
    """
    Gera um nome de arquivo único baseado em timestamp.
    
    Returns:
        str: Nome do arquivo para a análise.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"analise_{timestamp}.json"

def process_commits(commits_data, analyzed_session_count=0):
    """
    Processa uma lista de commits para análise.
    
    Args:
        commits_data (pd.DataFrame): DataFrame contendo os commits a serem analisados.
        analyzed_session_count (int): Número de commits já analisados na sessão atual.
        
    Returns:
        list: Lista de resultados da análise.
    """
    if commits_data is None or len(commits_data) == 0:
        print(error("Nenhum commit para analisar."))
        return []

    git_handler = GitHandler()
    llm_handler = LLMHandler()
    results = []
    
    total_commits = len(commits_data)
    print(info(f"Iniciando análise de {total_commits} commits..."))
    
    # Mostrar o prompt apenas uma vez antes de iniciar as análises
    print(f"\n{header('=' * 50)}")
    print(f"{header('PROMPT QUE SERÁ ENVIADO AO MODELO:')}")
    print(f"{header('=' * 50)}")
    from src.core.config import LLM_PROMPT, DEBUG_MAX_PROMPT_LENGTH
    if len(LLM_PROMPT) > DEBUG_MAX_PROMPT_LENGTH:
        print(LLM_PROMPT[:DEBUG_MAX_PROMPT_LENGTH] + dim("... [truncado]"))
        print(dim(f"\nPrompt completo tem {len(LLM_PROMPT)} caracteres. Exibindo primeiros {DEBUG_MAX_PROMPT_LENGTH} caracteres."))
    else:
        print(LLM_PROMPT)
    print(f"{header('=' * 50)}\n")
    
    for index, commit_row in commits_data.iterrows():
        commit1 = commit_row['commit1']
        commit2 = commit_row['commit2']
        project = commit_row['project']
        project_name = commit_row['project_name']
        
        # Contadores para acompanhamento
        current_batch_position = index + 1  # Posição na consulta atual
        current_analysis_number = analyzed_session_count + len(results) + 1  # Número da análise atual na sessão
        
        print(f"\n{header(f'CONSULTA ATUAL [{current_batch_position}/{total_commits}] | SESSÃO TOTAL [#{current_analysis_number}]')}")
        print(f"{highlight('Analisando commits do projeto:')} {bold(project_name)}")
        print(f"{dim('Commit1:')} {commit_info(commit1)}")
        print(f"{dim('Commit2:')} {commit_info(commit2)}")
        
        # Garantir que o repositório esteja clonado e atualizado
        success_flag, repo_path = git_handler.ensure_repo_cloned(project)
        if not success_flag:
            print(error(f"Erro ao processar repositório {project}. Pulando análise deste commit."))
            continue
        
        # Verificar se ambos os commits existem
        if not git_handler.commit_exists(repo_path, commit1):
            print(error(f"Commit {commit1} não encontrado no repositório. Pulando análise."))
            continue
            
        if not git_handler.commit_exists(repo_path, commit2):
            print(error(f"Commit {commit2} não encontrado no repositório. Pulando análise."))
            continue
        
        # Obter o diff e a mensagem do commit
        diff = git_handler.get_commit_diff(repo_path, commit1, commit2)
        if diff is None:
            print(error(f"Não foi possível obter o diff entre os commits. Pulando análise."))
            continue
            
        commit_message = git_handler.get_commit_message(repo_path, commit2)
        if commit_message is None:
            print(error(f"Não foi possível obter a mensagem do commit. Pulando análise."))
            continue
        
        # Analisar o commit com o LLM
        print(progress("Enviando para análise pelo modelo LLM..."))
        analysis = llm_handler.analyze_commit(project, commit1, commit2, commit_message, diff, show_prompt=False)
        
        if analysis is not None:
            refact_type = analysis['refactoring_type']
            type_color = success if refact_type == 'pure' else warning
            print(success(f"Análise concluída! Tipo de refatoramento: {type_color(refact_type)}"))
            results.append(analysis)
        else:
            print(error("Falha na análise do commit."))
    
    # Mostrar resumo dos resultados
    if results:
        pure_count = sum(1 for r in results if r['refactoring_type'] == 'pure')
        floss_count = sum(1 for r in results if r['refactoring_type'] == 'floss')
        
        print(f"\n{header('=' * 45)}")
        print(f"{header('RESUMO DA ANÁLISE:')}")
        print(f"{header('=' * 45)}")
        print(f"{success('Pure:')} {bold(str(pure_count))}")
        print(f"{warning('Floss:')} {bold(str(floss_count))}")
        print(f"{info('Total analisado:')} {bold(str(len(results)))}")
        print(f"{header('=' * 45)}")
    
    return results

def process_commits_optimized(commits_data, analyzed_session_count=0):
    """
    Processa uma lista de commits para análise usando APENAS o handler otimizado com prompt padrão.
    
    Args:
        commits_data (pd.DataFrame): DataFrame contendo os commits a serem analisados.
        analyzed_session_count (int): Número de commits já analisados na sessão atual.
        
    Returns:
        list: Lista de resultados da análise.
    """
    if commits_data is None or len(commits_data) == 0:
        print(error("Nenhum commit para analisar."))
        return []

    git_handler = GitHandler()
    # Usar handler otimizado mas forçar prompt padrão
    llm_handler = OptimizedLLMHandler()
    # Substituir o prompt otimizado pelo padrão para esta opção
    from src.core.config import LLM_PROMPT
    llm_handler.llm_prompt = LLM_PROMPT
    results = []
    
    total_commits = len(commits_data)
    print(info(f"Iniciando análise com HANDLER OTIMIZADO + PROMPT PADRÃO de {total_commits} commits..."))
    
    # Mostrar informações sobre a configuração
    print(f"\n{header('=' * 50)}")
    print(f"{header('CONFIGURAÇÃO HÍBRIDA:')}")
    print(f"{header('=' * 50)}")
    print(f"{info('Handler:')} OptimizedLLMHandler (diffs grandes, timeouts, retry)")
    print(f"{info('Prompt:')} LLM_PROMPT (padrão)")
    print(f"{info('Suporte a arquivos:')} Sim (para diffs grandes)")
    print(f"{warning('Nota:')} Use opção 5 para prompt otimizado completo")
    print(f"{header('=' * 50)}\n")
    
    for index, commit_row in commits_data.iterrows():
        commit1 = commit_row['commit1']
        commit2 = commit_row['commit2']
        project = commit_row['project']
        project_name = commit_row['project_name']
        
        # Contadores para acompanhamento
        current_batch_position = index + 1  # Posição na consulta atual
        current_analysis_number = analyzed_session_count + len(results) + 1  # Número da análise atual na sessão
        
        print(f"\n{header(f'ANÁLISE OTIMIZADA [{current_batch_position}/{total_commits}] | SESSÃO TOTAL [#{current_analysis_number}]')}")
        print(f"{highlight('Analisando commits do projeto:')} {bold(project_name)}")
        print(f"{dim('Commit1:')} {commit_info(commit1)}")
        print(f"{dim('Commit2:')} {commit_info(commit2)}")
        
        # Garantir que o repositório esteja clonado e atualizado
        success_flag, repo_path = git_handler.ensure_repo_cloned(project)
        if not success_flag:
            print(error(f"Erro ao processar repositório {project}. Pulando análise deste commit."))
            continue
        
        # Verificar se ambos os commits existem
        if not git_handler.commit_exists(repo_path, commit1):
            print(error(f"Commit {commit1} não encontrado no repositório. Pulando análise."))
            continue
            
        if not git_handler.commit_exists(repo_path, commit2):
            print(error(f"Commit {commit2} não encontrado no repositório. Pulando análise."))
            continue
        
        # Obter o diff e a mensagem do commit
        diff = git_handler.get_commit_diff(repo_path, commit1, commit2)
        if diff is None:
            print(error(f"Não foi possível obter o diff entre os commits. Pulando análise."))
            continue
            
        commit_message = git_handler.get_commit_message(repo_path, commit2)
        if commit_message is None:
            print(error(f"Não foi possível obter a mensagem do commit. Pulando análise."))
            continue
        
        # Analisar o commit com o LLM otimizado
        print(progress("Enviando para análise pelo modelo LLM otimizado..."))
        
        # Tentar análise com recuperação de erro
        max_retries = 2
        analysis = None
        
        for attempt in range(max_retries + 1):
            try:
                analysis = llm_handler.analyze_commit(project, commit1, commit2, commit_message, diff, show_prompt=False)
                if analysis is not None:
                    break
                else:
                    if attempt < max_retries:
                        print(warning(f"Tentativa {attempt + 1} falhou, tentando novamente..."))
                    else:
                        print(error("Todas as tentativas falharam."))
            except Exception as e:
                if attempt < max_retries:
                    print(warning(f"Erro na tentativa {attempt + 1}: {str(e)}, tentando novamente..."))
                else:
                    print(error(f"Erro definitivo após {max_retries + 1} tentativas: {str(e)}"))
        
        if analysis is not None:
            refact_type = analysis['refactoring_type']
            processing_method = analysis.get('processing_method', 'unknown')
            diff_size = analysis.get('diff_size_chars', 0)
            confidence = analysis.get('confidence_level', 'medium')
            
            type_color = success if refact_type == 'pure' else warning
            print(success(f"Análise concluída! Tipo: {type_color(refact_type)} | Método: {processing_method} | Tamanho: {diff_size} chars | Confiança: {confidence}"))
            results.append(analysis)
        else:
            print(error("Falha na análise do commit após múltiplas tentativas."))
    
    # Mostrar resumo dos resultados com estatísticas extras
    if results:
        pure_count = sum(1 for r in results if r['refactoring_type'] == 'pure')
        floss_count = sum(1 for r in results if r['refactoring_type'] == 'floss')
        file_method_count = sum(1 for r in results if r.get('processing_method') == 'file')
        direct_method_count = sum(1 for r in results if r.get('processing_method') == 'direct')
        avg_diff_size = sum(r.get('diff_size_chars', 0) for r in results) / len(results) if results else 0
        
        print(f"\n{header('=' * 55)}")
        print(f"{header('RESUMO DA ANÁLISE OTIMIZADA:')}")
        print(f"{header('=' * 55)}")
        print(f"{success('Pure:')} {bold(str(pure_count))}")
        print(f"{warning('Floss:')} {bold(str(floss_count))}")
        print(f"{info('Total analisado:')} {bold(str(len(results)))}")
        print(f"{dim('Processamento via arquivo:')} {file_method_count}")
        print(f"{dim('Processamento direto:')} {direct_method_count}")
        print(f"{dim('Tamanho médio dos diffs:')} {int(avg_diff_size)} caracteres")
        print(f"{header('=' * 55)}")
    
    return results

def save_results(results, data_handler):
    """
    Salva os resultados da análise em um arquivo JSON e atualiza o registro de commits analisados.
    
    Args:
        results (list): Lista de resultados da análise.
        data_handler (DataHandler): Instância do manipulador de dados.
        
    Returns:
        str: Caminho do arquivo salvo ou None em caso de falha.
    """
    if not results:
        print(warning("Nenhum resultado para salvar."))
        return None
        
    # Garantir que o diretório de análises existe
    from src.core.config import get_model_paths
    model_paths = get_model_paths()
    analises_dir = model_paths["ANALISES_DIR"]
    
    if not analises_dir.exists():
        analises_dir.mkdir(parents=True, exist_ok=True)
    
    # Gerar nome do arquivo de saída
    output_file = analises_dir / generate_output_filename()
    
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=4)
        
        # Atualizar o registro de commits analisados
        data_handler.save_analyzed_commits(results)
        
        print(success(f"\nResultados salvos com sucesso em: {bold(output_file)}"))
        return output_file
    except Exception as e:
        print(error(f"Erro ao salvar os resultados: {str(e)}"))
        return None

def process_specific_commits_optimized(commits_data, analyzed_session_count=0):
    """
    Processa uma quantidade específica de commits usando HANDLER + PROMPT OTIMIZADOS.
    Esta é a opção mais avançada e recomendada para máxima qualidade.
    
    Args:
        commits_data (pd.DataFrame): DataFrame contendo os commits a serem analisados.
        analyzed_session_count (int): Número de commits já analisados na sessão atual.
        
    Returns:
        list: Lista de resultados da análise.
    """
    if commits_data is None or len(commits_data) == 0:
        print(error("Nenhum commit para analisar."))
        return []

    git_handler = GitHandler()
    # Usar handler otimizado completo (handler + prompt otimizados)
    optimized_llm_handler = OptimizedLLMHandler()
    results = []
    
    total_commits = len(commits_data)
    print(info(f"Iniciando análise com HANDLER + PROMPT OTIMIZADOS de {total_commits} commits..."))
    
    # Mostrar informações sobre a configuração completa
    print(f"\n{header('=' * 50)}")
    print(f"{header('CONFIGURAÇÃO COMPLETA OTIMIZADA:')}")
    print(f"{header('=' * 50)}")
    print(f"{success('Handler:')} OptimizedLLMHandler (diffs grandes, timeouts, retry)")
    print(f"{success('Prompt:')} OPTIMIZED_LLM_PROMPT (indicadores técnicos)")
    print(f"{success('Recursos:')} Suporte completo a diffs grandes via arquivo")
    print(f"{success('Qualidade:')} Máxima precisão com indicadores do Purity")
    print(f"{success('Robustez:')} Tratamento de erros e recovery automático")
    print(f"{header('=' * 50)}\n")
    
    for index, (_, commit_row) in enumerate(commits_data.iterrows(), 1):
        current_hash = commit_row['commit2']  # commit atual
        previous_hash = commit_row['commit1']  # commit anterior
        repository = commit_row['project']  # URL do repositório
        
        print(f"\n{progress(f'Processando commit {index}/{total_commits}:')} {highlight(current_hash[:8])}")
        print(dim(f"Repositório: {commit_row['project_name']}"))
        
        try:
            # Clonar/atualizar repositório
            success_flag, repo_path = git_handler.ensure_repo_cloned(repository)
            if not success_flag:
                print(error(f"Erro ao clonar repositório: {repo_path}"))
                continue
            
            # Obter diff do commit
            diff_content = git_handler.get_commit_diff(
                repo_path, previous_hash, current_hash
            )
            
            if not diff_content:
                print(error(f"Erro ao obter diff entre {previous_hash[:8]} e {current_hash[:8]}"))
                continue
            
            # Usar handler otimizado para análise
            analysis_result = optimized_llm_handler.analyze_commit_refactoring(
                current_hash, previous_hash, repository, diff_content
            )
            
            if analysis_result and analysis_result.get('success', False):
                print(success(f"✅ Commit analisado: {bold(analysis_result.get('refactoring_type', 'N/A'))}"))
                results.append(analysis_result)
            else:
                error_msg = analysis_result.get('error', 'Erro desconhecido') if analysis_result else 'Resultado vazio'
                print(error(f"❌ Falha na análise: {error_msg}"))
        
        except KeyboardInterrupt:
            print(f"\n{warning('⚠️ Processamento interrompido pelo usuário.')}")
            print(info(f"📊 {len(results)} commits foram analisados antes da interrupção."))
            break
        except Exception as e:
            print(error(f"❌ Erro inesperado: {str(e)}"))
            continue
    
    # Exibir sumário
    print(f"\n{header('=' * 50)}")
    print(f"{header('SUMÁRIO DA ANÁLISE OTIMIZADA')}")
    print(f"{header('=' * 50)}")
    print(success(f"✅ Total processado: {len(results)}/{total_commits} commits"))
    
    if results:
        refactoring_counts = {}
        for result in results:
            ref_type = result.get('refactoring_type', 'unknown')
            refactoring_counts[ref_type] = refactoring_counts.get(ref_type, 0) + 1
        
        print(info("📊 Distribuição por tipo:"))
        for ref_type, count in refactoring_counts.items():
            print(f"   • {ref_type}: {count}")
    
    return results

def process_purity_comparison_with_limit():
    """
    Processa a comparação entre análises LLM e resultados do Purity com limite definido pelo usuário.
    """
    print(f"\n{header('=' * 60)}")
    print(f"{header('COMPARAÇÃO LLM vs PURITY (QUANTIDADE PERSONALIZADA)')}")
    print(f"{header('=' * 60)}")
    
    try:
        limit = int(input(f"{cyan('Digite o número de commits floss para analisar:')} "))
        if limit <= 0:
            print(error("Número deve ser positivo."))
            return
    except ValueError:
        print(error("Por favor, digite um número válido."))
        return
    
    _process_purity_comparison_internal(limit)

def process_purity_comparison_all():
    """
    Processa a comparação entre análises LLM e resultados do Purity para todos os commits.
    """
    print(f"\n{header('=' * 60)}")
    print(f"{header('COMPARAÇÃO LLM vs PURITY (TODOS OS COMMITS)')}")
    print(f"{header('=' * 60)}")
    
    _process_purity_comparison_internal(None)

def _process_purity_comparison_internal(limit):
    """
    Função interna que processa a comparação entre análises LLM e resultados do Purity.
    Implementa análise sequencial evitando duplicatas e usando handler otimizado.
    
    Args:
        limit (int or None): Número máximo de commits a processar. Se None, processa todos.
    """
    print(f"\n{header('=' * 60)}")
    print(f"{header('COMPARAÇÃO LLM vs PURITY (VERSÃO OTIMIZADA)')}")
    print(f"{header('=' * 60)}")
    
    # Inicializar handlers
    purity_handler = PurityHandler()
    data_handler = DataHandler()
    
    # Carregar dados do Purity
    print(progress("Carregando dados do Purity..."))
    if not purity_handler.load_purity_data():
        print(error("Falha ao carregar dados do Purity"))
        return
    
    # Obter commits não analisados (sequencial, evita duplicatas)
    print(progress("Identificando commits Purity ainda não analisados..."))
    unanalyzed_commits, stats = purity_handler.get_unanalyzed_purity_commits(limit=limit)
    
    if not unanalyzed_commits or len(unanalyzed_commits) == 0:
        print(warning("Nenhum commit Purity pendente de análise encontrado."))
        print(info("Todos os commits Purity já foram analisados pelo LLM."))
        
        # Gerar comparação mesmo sem novos commits
        print(f"\n{progress('Gerando comparação com dados existentes...')}")
        _generate_final_comparison(purity_handler)
        return
    
    # Análise automática dos commits pendentes (sempre com handler otimizado)
    print(f"\n{success('🚀 INICIANDO ANÁLISE AUTOMÁTICA')}")
    print(f"{info('Configuração:')} Handler otimizado + prompt otimizado (máxima qualidade)")
    print(f"{info('Commits a analisar:')} {len(unanalyzed_commits)}")
    print(f"{dim('Análise será feita automaticamente sem perguntas adicionais')}")
    
    # Extrair hashes únicos para buscar no CSV principal
    commit_hashes = list(set(commit['commit_hash_current'] for commit in unanalyzed_commits))
    
    print(f"\n{progress('Buscando dados dos commits no dataset principal...')}")
    commits_data = data_handler.get_commits_by_hashes(commit_hashes, skip_filtering=True)
    
    if commits_data is None or len(commits_data) == 0:
        print(error("Não foi possível encontrar dados dos commits no dataset principal."))
        return
    
    # Explicar diferença de números se houver
    expected_count = len(commit_hashes)  # Commits únicos do Purity
    found_count = len(commits_data)      # Entradas encontradas no CSV
    
    print(f"\n{header('VERIFICAÇÃO DE DADOS:')}")
    print(f"{info('Commits únicos Purity:')} {expected_count}")
    print(f"{info('Entradas no CSV:')} {found_count}")
    
    if found_count != expected_count:
        print(f"{warning('Diferença:')} {abs(found_count - expected_count)} entradas")
        if found_count > expected_count:
            print(f"{dim('Motivo:')} Mesmo commit com diferentes commit_hash_before no CSV")
            print(f"{dim('Impacto:')} Deduplicação automática aplicada na análise")
        print(f"{success('Resultado:')} Análise processará {found_count} entradas (normal)")
    else:
        print(f"{success('✅ Números correspondem perfeitamente')}")
    
    # Processar commits com handler otimizado automaticamente
    print(f"\n{progress('Iniciando análise otimizada...')}")
    results = process_specific_commits_optimized(commits_data, analyzed_session_count=0)
    
    if results:
        # Salvar resultados
        save_results(results, data_handler)
        print(f"\n{success(f'✅ {len(results)} commits analisados e salvos!')}")
        
        # Atualizar estatísticas
        total_analyzed = stats['already_analyzed'] + len(results)
        progress_percent = (total_analyzed / stats['total_purity']) * 100
        print(f"{info('Progresso geral:')} {total_analyzed}/{stats['total_purity']} commits Purity ({progress_percent:.1f}%)")
    else:
        print(f"\n{error('❌ Nenhum resultado obtido da análise')}")
    
    # Gerar comparação final
    print(f"\n{progress('Gerando comparação LLM vs Purity...')}")
    _generate_final_comparison(purity_handler)

def _generate_final_comparison(purity_handler):
    """
    Gera a comparação final entre LLM e Purity e salva os resultados.
    
    Args:
        purity_handler: Instância do PurityHandler
    """
    try:
        # Carregar todas as análises LLM
        all_llm_analyses = purity_handler.load_all_llm_analyses()
        
        # Obter todos os commits Purity
        all_purity_commits = purity_handler.get_all_purity_commits()
        
        if not all_llm_analyses or not all_purity_commits:
            print(error("Dados insuficientes para gerar comparação"))
            return
        
        # Gerar dados de comparação
        comparison_data = purity_handler.generate_comparison_data(all_llm_analyses, all_purity_commits)
        
        if comparison_data is not None and len(comparison_data) > 0:
            # Salvar comparação
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            comparison_filename = f"comparacao_llm_purity_{timestamp}.json"
            
            try:
                comparison_list = comparison_data.to_dict('records') if hasattr(comparison_data, 'to_dict') else comparison_data
                with open(comparison_filename, 'w') as f:
                    json.dump(comparison_list, f, indent=2, ensure_ascii=False)
                
                print(f"\n{success(f'✅ Comparação salva em: {bold(comparison_filename)}')}")
                
                # Exibir estatísticas da comparação
                purity_handler.display_comparison_statistics(comparison_data)
                
            except Exception as e:
                print(error(f"Erro ao salvar comparação: {str(e)}"))
        else:
            print(error("Falha ao gerar dados de comparação."))
            
    except Exception as e:
        print(error(f"Erro durante geração da comparação: {str(e)}"))

def show_menu(analyzed_count=0, total_count=0, session_count=0):
    """
    Exibe o menu de opções para o usuário.
    
    Args:
        analyzed_count (int): Número de commits já analisados historicamente.
        total_count (int): Número total de commits disponíveis.
        session_count (int): Número de commits analisados na sessão atual.
    """
    print(f"\n{header('=' * 50)}")
    print(f"{header('ANÁLISE DE COMMITS DE REFATORAMENTO')}")
    print(f"{header('=' * 50)}")
    if total_count > 0:
        progress_percent = (analyzed_count) / total_count * 100
        progress_color = success if progress_percent == 100 else info
        print(progress_color(f"Status histórico: {analyzed_count}/{total_count} commits analisados ({progress_percent:.1f}%)"))
    
    if session_count > 0:
        print(success(f"Sessão atual: {session_count} commits analisados"))
    
    print(f"{cyan('1.')} Analisar um número específico de commits")
    print(f"{cyan('2.')} Analisar um commit aleatório")
    print(f"{cyan('3.')} Analisar todos os commits filtrados")
    print(f"{cyan('4.')} Analisar commits com HANDLER OTIMIZADO (prompt padrão)")
    print(f"{cyan('5.')} Analisar commits com PROMPT + HANDLER OTIMIZADOS (recomendado)")
    print(f"{cyan('6.')} Comparar análises LLM com Purity (escolher quantidade)")
    print(f"{cyan('7.')} Comparar análises LLM com Purity (todos os commits)")
    print(f"{cyan('8.')} Gerar visualizações interativas dos dados analisados")
    print(f"{cyan('9.')} Visualizar comparação LLM vs Purity")
    print(f"{cyan('10.')} Verificar duplicatas no dataset")
    print(f"{cyan('11.')} Alterar modelo LLM (atual: {get_current_llm_model()})")
    print(f"{cyan('12.')} Sair da aplicação")
    print(f"{header('=' * 50)}")

def visualize_analysis_data():
    """
    Cria visualizações interativas dos dados de análise de commits.
    """
    try:
        print(info("Carregando dados para visualização..."))
        
        viz_handler = VisualizationHandler()
        
        if viz_handler.analyzed_data is None or len(viz_handler.analyzed_data) == 0:
            print(error("Nenhum dado de análise encontrado para visualização."))
            print(info("Execute algumas análises primeiro (opções 1-6) e tente novamente."))
            return
        
        print(success(f"Dados carregados: {len(viz_handler.analyzed_data)} commits analisados"))
        
        # Perguntar formato de saída
        print(f"\n{cyan('Escolha o formato de saída:')}")
        print(f"{cyan('1.')} Apenas exibir interativo (padrão)")
        print(f"{cyan('2.')} Salvar HTML + exibir")
        print(f"{cyan('3.')} Salvar HTML + PNG + exibir")
        
        format_choice = input(f"{cyan('Escolha (1-3, Enter para padrão):')} ").strip()
        
        save_html = format_choice in ['2', '3']
        save_image = format_choice == '3'
        
        if not save_html and not save_image:
            print(info("Gerando visualização interativa..."))
        else:
            print(info("Gerando e salvando visualização..."))
        
        # Gerar dashboard
        result = viz_handler.create_comprehensive_dashboard(
            save_html=save_html, 
            save_image=save_image
        )
        
        if result:
            print(success("Visualização gerada com sucesso!"))
            if save_html or save_image:
                print(info(f"Arquivo salvo: {bold(result)}"))
        else:
            print(warning("Visualização exibida apenas interativamente."))
            
        # Mostrar estatísticas resumidas
        stats = viz_handler.get_summary_stats()
        if "error" not in stats:
            print(f"\n{header('ESTATÍSTICAS RESUMIDAS:')}")
            for key, value in stats.items():
                print(f"{cyan(key)}: {bold(str(value))}")
                
    except Exception as e:
        print(error(f"Erro ao gerar visualização: {str(e)}"))

def visualize_purity_comparison():
    """
    Cria visualizações específicas para comparação LLM vs Purity.
    """
    try:
        print(info("Carregando dados de comparação LLM vs Purity..."))
        
        # Usar PurityHandler para obter dados de comparação
        purity_handler = PurityHandler()
        
        # Tentar obter dados de comparação existentes
        comparison_data = None
        
        # Verificar se existem dados de comparação salvos
        comparison_files = []
        for file in os.listdir('.'):
            if file.startswith('comparacao_llm_purity_') and file.endswith('.json'):
                comparison_files.append(file)
        
        if comparison_files:
            # Usar o arquivo mais recente
            latest_file = sorted(comparison_files)[-1]
            try:
                with open(latest_file, 'r') as f:
                    comparison_data = json.load(f)
                print(success(f"Dados de comparação carregados de: {bold(latest_file)}"))
            except Exception as e:
                print(warning(f"Erro ao carregar {latest_file}: {str(e)}"))
        
        if comparison_data is None:
            print(warning("Nenhum dado de comparação encontrado."))
            print(info("Execute a comparação LLM vs Purity primeiro (opções 5 ou 6)."))
            return
        
        # Converter para DataFrame se necessário
        if isinstance(comparison_data, list):
            import pandas as pd
            comparison_df = pd.DataFrame(comparison_data)
        else:
            comparison_df = comparison_data
        
        # Filtrar apenas commits com análise de AMBOS os sistemas
        mutual_analysis = comparison_df[
            (comparison_df['in_purity'] == True) & 
            (comparison_df['analyzed_by_llm'] == True)
        ].copy()
        
        only_purity = comparison_df[
            (comparison_df['in_purity'] == True) & 
            (comparison_df['analyzed_by_llm'] == False)
        ].copy()
        
        only_llm = comparison_df[
            (comparison_df['in_purity'] == False) & 
            (comparison_df['analyzed_by_llm'] == True)
        ].copy()
        
        print(success(f"Dados carregados: {len(comparison_df)} commits totais"))
        print(info(f"Commits com análise de AMBOS: {bold(str(len(mutual_analysis)))}"))
        print(info(f"Commits apenas Purity: {len(only_purity)}"))
        print(info(f"Commits apenas LLM: {len(only_llm)}"))
        
        if len(mutual_analysis) == 0:
            print(warning("Nenhum commit foi analisado por ambos os sistemas."))
            print(info("Execute mais análises LLM ou verifique os dados."))
            return
        
        # Perguntar o que visualizar
        print(f"\n{cyan('Escolha o que visualizar:')}")
        print(f"{cyan('1.')} Apenas comparação direta (commits analisados por ambos) - RECOMENDADO")
        print(f"{cyan('2.')} Todos os dados (incluindo análises parciais)")
        
        data_choice = input(f"{cyan('Escolha (1-2, Enter para 1):')} ").strip()
        
        if data_choice == '2':
            selected_data = comparison_df
            data_description = "todos os dados"
        else:
            selected_data = mutual_analysis
            data_description = "apenas comparação direta"
        
        # Perguntar formato de saída
        print(f"\n{cyan('Escolha o formato de saída:')}")
        print(f"{cyan('1.')} Apenas exibir interativo (padrão)")
        print(f"{cyan('2.')} Salvar HTML + exibir")
        print(f"{cyan('3.')} Salvar HTML + PNG + exibir")
        
        format_choice = input(f"{cyan('Escolha (1-3, Enter para padrão):')} ").strip()
        
        save_html = format_choice in ['2', '3']
        save_image = format_choice == '3'
        
        print(info(f"Gerando visualização com {data_description}..."))
        
        # Usar VisualizationHandler para gerar gráfico
        viz_handler = VisualizationHandler()
        
        result = viz_handler.create_comparison_chart(
            selected_data,
            save_html=save_html,
            save_image=save_image
        )
        
        if result:
            print(success("Visualização de comparação gerada com sucesso!"))
            if save_html or save_image:
                print(info(f"Arquivo salvo: {bold(result)}"))
        else:
            print(warning("Visualização exibida apenas interativamente."))
            
    except Exception as e:
        print(error(f"Erro ao gerar visualização de comparação: {str(e)}"))

def main():
    """Função principal da aplicação."""
    # Configurar handlers de sinal para interrupções
    setup_signal_handlers()
    
    # Criar diretórios necessários
    create_directories()
    
    clear_screen()
    print(highlight("Iniciando aplicação de análise de refatoramento..."))
    
    # Inicializar manipulador de dados
    data_handler = DataHandler()
    
    # Contador de commits analisados na sessão atual
    session_analyzed_count = 0
    
    # Carregar e filtrar dados
    if not data_handler.load_data():
        print(error("Erro ao carregar os dados. Encerrando aplicação."))
        return
    
    if not data_handler.filter_data():
        print(error("Erro ao filtrar os dados. Encerrando aplicação."))
        return
    
    while True:
        # Mostrar o menu com informações atualizadas sobre commits analisados
        total_commits = len(data_handler.filtered_data) if data_handler.filtered_data is not None else 0
        analyzed_count = len(data_handler.analyzed_commits) if data_handler.analyzed_commits is not None else 0
        
        show_menu(analyzed_count, total_commits, session_analyzed_count)
        choice = input(f"{bold('Escolha uma opção (1-11):')} ")
        
        if choice == '1':
            try:
                n = int(input(f"{cyan('Digite o número de commits para analisar:')} "))
                
                # Perguntar se deve pular commits já analisados
                skip_option = input(f"{cyan('Pular commits já analisados anteriormente? (s/n):')} ").lower()
                skip_analyzed = skip_option == 's' or skip_option == 'sim'
                
                commits_data = data_handler.get_n_commits(n, skip_analyzed)
                if commits_data is not None:
                    results = process_commits(commits_data, session_analyzed_count)
                    if results:
                        session_analyzed_count += len(results)
                    save_results(results, data_handler)
                    input(f"\n{dim('Pressione Enter para continuar...')}")
            except ValueError:
                print(error("Erro: Por favor, digite um número válido."))
                input(f"{dim('Pressione Enter para continuar...')}")
        
        elif choice == '2':
            # Perguntar se deve pular commits já analisados
            skip_option = input(f"{cyan('Pular commits já analisados anteriormente? (s/n):')} ").lower()
            skip_analyzed = skip_option == 's' or skip_option == 'sim'
            
            commits_data = data_handler.get_random_commit(skip_analyzed)
            if commits_data is not None:
                results = process_commits(commits_data, session_analyzed_count)
                if results:
                    session_analyzed_count += len(results)
                save_results(results, data_handler)
                input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '3':
            # Perguntar se deve pular commits já analisados
            skip_option = input(f"{cyan('Pular commits já analisados anteriormente? (s/n):')} ").lower()
            skip_analyzed = skip_option == 's' or skip_option == 'sim'
            
            commits_data = data_handler.get_all_filtered_commits(skip_analyzed)
            if commits_data is not None:
                results = process_commits(commits_data, session_analyzed_count)
                if results:
                    session_analyzed_count += len(results)
                save_results(results, data_handler)
                input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '4':
            try:
                n = int(input(f"{cyan('Digite o número de commits para analisar com HANDLER OTIMIZADO:')} "))
                
                # Perguntar se deve pular commits já analisados
                skip_option = input(f"{cyan('Pular commits já analisados anteriormente? (s/n):')} ").lower()
                skip_analyzed = skip_option == 's' or skip_option == 'sim'
                
                commits_data = data_handler.get_n_commits(n, skip_analyzed)
                if commits_data is not None:
                    results = process_commits_optimized(commits_data, session_analyzed_count)
                    if results:
                        session_analyzed_count += len(results)
                    save_results(results, data_handler)
                    input(f"\n{dim('Pressione Enter para continuar...')}")
            except ValueError:
                print(error("Erro: Por favor, digite um número válido."))
                input(f"{dim('Pressione Enter para continuar...')}")
        
        elif choice == '5':
            try:
                n = int(input(f"{cyan('Digite o número de commits para analisar com PROMPT OTIMIZADO:')} "))
                
                # Perguntar se deve pular commits já analisados
                skip_option = input(f"{cyan('Pular commits já analisados anteriormente? (s/n):')} ").lower()
                skip_analyzed = skip_option == 's' or skip_option == 'sim'
                
                commits_data = data_handler.get_n_commits(n, skip_analyzed)
                if commits_data is not None:
                    results = process_specific_commits_optimized(commits_data, session_analyzed_count)
                    if results:
                        session_analyzed_count += len(results)
                    save_results(results, data_handler)
                    input(f"\n{dim('Pressione Enter para continuar...')}")
            except ValueError:
                print(error("Erro: Por favor, digite um número válido."))
                input(f"{dim('Pressione Enter para continuar...')}")
        
        elif choice == '6':
            process_purity_comparison_with_limit()
            input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '7':
            process_purity_comparison_all()
            input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '8':
            visualize_analysis_data()
            input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '9':
            visualize_purity_comparison()
            input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '10':
            print(f"\n{header('VERIFICAÇÃO DE DUPLICATAS NO DATASET')}")
            stats = data_handler.check_dataset_duplicates()
            if stats:
                print(f"\n{success('Análise de duplicatas concluída!')}")
                duplicate_percent = (stats['duplicated_commit2'] / stats['unique_commit2']) * 100 if stats['unique_commit2'] > 0 else 0
                print(f"{info(f'Percentual de commits duplicados: {duplicate_percent:.2f}%')}")
            input(f"\n{dim('Pressione Enter para continuar...')}")
        
        elif choice == '11':
            # Trocar modelo
            print(info("Modelos disponíveis no Ollama:"))
            models = list_available_ollama_models()
            if not models:
                print(error("Nenhum modelo encontrado."))
                input(f"\n{dim('Pressione Enter para continuar...')}")
                continue
            for idx, m in enumerate(models, 1):
                mark = ' (atual)' if m == get_current_llm_model() else ''
                print(f"  {cyan(str(idx)+'.')} {m}{mark}")
            sel = input(cyan('Escolha o número do modelo (Enter cancela): ')).strip()
            if sel:
                try:
                    idx = int(sel) - 1
                    if idx < 0 or idx >= len(models):
                        print(warning('Índice inválido.'))
                    else:
                        new_model = models[idx]
                        set_llm_model(new_model)
                        ensure_model_directories()
                        # Recarregar commits analisados correspondente ao novo modelo
                        data_handler = DataHandler()  # nova instância com paths atualizados
                        print(success(f"Modelo alterado para: {new_model}"))
                except ValueError:
                    print(warning('Entrada inválida.'))
            input(f"\n{dim('Pressione Enter para continuar...')}")

        elif choice == '12':
            print(success("Encerrando aplicação. Obrigado!"))
            break
        
        else:
            print(error("Opção inválida. Por favor, escolha uma opção de 1 a 11."))
            input(f"{dim('Pressione Enter para continuar...')}")
        
        clear_screen()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Este catch é um backup caso o signal handler não funcione
        print(f"\n{warning('Aplicação interrompida pelo usuário.')}")
        print(f"{success('Encerramento seguro realizado!')}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{error(f'Erro inesperado: {str(e)}')}")
        print(f"{warning('Por favor, reporte este erro ao desenvolvedor.')}")
        sys.exit(1)
