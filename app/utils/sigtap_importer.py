import os
import zipfile
import tempfile
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple
from app.procedures_models import Procedure, Cid, ProcedureCid
from app.models import db

logger = logging.getLogger(__name__)


class SIGTAPImporter:
    
    LAYOUT_PROCEDIMENTO = {
        'CO_PROCEDIMENTO': (0, 10),
        'NO_PROCEDIMENTO': (10, 260),
        'TP_COMPLEXIDADE': (260, 261),
        'TP_SEXO': (261, 262),
        'QT_MAXIMA_EXECUCAO': (262, 266),
        'QT_DIAS_PERMANENCIA': (266, 270),
        'QT_PONTOS': (270, 274),
        'VL_IDADE_MINIMA': (274, 278),
        'VL_IDADE_MAXIMA': (278, 282),
        'VL_SH': (282, 294),
        'VL_SA': (294, 306),
        'VL_SP': (306, 318),
        'CO_FINANCIAMENTO': (318, 320),
        'CO_RUBRICA': (320, 326),
        'QT_TEMPO_PERMANENCIA': (326, 330),
        'DT_COMPETENCIA': (330, 336),
    }
    
    LAYOUT_CID = {
        'CO_CID': (0, 4),
        'NO_CID': (4, 104),
    }
    
    LAYOUT_PROCEDIMENTO_CID = {
        'CO_PROCEDIMENTO': (0, 10),
        'CO_CID': (10, 14),
        'ST_PRINCIPAL': (14, 15),
    }
    
    def __init__(self):
        self.stats = {
            'procedures': {'total': 0, 'inserted': 0, 'updated': 0, 'deactivated': 0, 'errors': 0},
            'cids': {'total': 0, 'inserted': 0, 'updated': 0, 'deactivated': 0, 'errors': 0},
            'relationships': {'total': 0, 'inserted': 0, 'errors': 0},
            'error_messages': []
        }
    
    def parse_procedimento_line(self, line: str) -> Dict:
        data = {}
        try:
            for field, (start, end) in self.LAYOUT_PROCEDIMENTO.items():
                value = line[start:end].strip()
                
                if field == 'CO_PROCEDIMENTO':
                    data['code'] = value
                elif field == 'NO_PROCEDIMENTO':
                    data['description'] = value.replace('�', 'Ã').strip()
                elif field == 'TP_COMPLEXIDADE':
                    data['complexity_type'] = value if value else None
                elif field == 'TP_SEXO':
                    data['gender_type'] = value if value else None
                elif field in ['QT_MAXIMA_EXECUCAO', 'QT_DIAS_PERMANENCIA', 'QT_PONTOS', 
                              'VL_IDADE_MINIMA', 'VL_IDADE_MAXIMA', 'QT_TEMPO_PERMANENCIA']:
                    try:
                        data[field.lower()] = int(value) if value and value.isdigit() else None
                    except ValueError:
                        data[field.lower()] = None
                elif field in ['VL_SH', 'VL_SA', 'VL_SP']:
                    try:
                        if value and value.isdigit():
                            data[field.lower()] = Decimal(value) / 100
                        else:
                            data[field.lower()] = None
                    except (ValueError, InvalidOperation):
                        data[field.lower()] = None
                elif field == 'CO_FINANCIAMENTO':
                    data['financing_code'] = value if value else None
                elif field == 'CO_RUBRICA':
                    data['rubric_code'] = value if value else None
                elif field == 'DT_COMPETENCIA':
                    data['competence_date'] = value if value else None
            
            return data
        except Exception as e:
            logger.error(f"Erro ao parsear linha: {str(e)}")
            return None
    
    def parse_cid_line(self, line: str) -> Dict:
        data = {}
        try:
            for field, (start, end) in self.LAYOUT_CID.items():
                value = line[start:end].strip()
                if field == 'CO_CID':
                    data['code'] = value
                elif field == 'NO_CID':
                    data['description'] = value.replace('�', 'Ã').strip()
            return data
        except Exception as e:
            logger.error(f"Erro ao parsear linha CID: {str(e)}")
            return None
    
    def parse_procedimento_cid_line(self, line: str) -> Dict:
        data = {}
        try:
            for field, (start, end) in self.LAYOUT_PROCEDIMENTO_CID.items():
                value = line[start:end].strip()
                if field == 'CO_PROCEDIMENTO':
                    data['procedure_code'] = value
                elif field == 'CO_CID':
                    data['cid_code'] = value
            return data
        except Exception as e:
            logger.error(f"Erro ao parsear linha relacionamento: {str(e)}")
            return None
    
    def extract_zip(self, zip_path: str) -> Dict[str, str]:
        temp_dir = tempfile.mkdtemp()
        files_found = {}
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_lower = file.lower()
                    if file_lower == 'tb_procedimento.txt':
                        files_found['procedimento'] = os.path.join(root, file)
                    elif file_lower == 'tb_cid.txt':
                        files_found['cid'] = os.path.join(root, file)
                    elif file_lower == 'rl_procedimento_cid.txt':
                        files_found['procedimento_cid'] = os.path.join(root, file)
            
            if 'procedimento' not in files_found:
                raise FileNotFoundError("Arquivo tb_procedimento.txt não encontrado no ZIP")
            
            files_found['temp_dir'] = temp_dir
            return files_found
        except Exception as e:
            logger.error(f"Erro ao extrair ZIP: {str(e)}")
            raise
    
    def import_procedures_from_file(self, file_path: str, encoding: str = 'latin-1') -> Dict:
        logger.info(f"Iniciando importação de procedimentos: {file_path}")
        
        existing_codes = {p.code for p in Procedure.query.with_entities(Procedure.code).all()}
        imported_codes = set()
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                for line_num, line in enumerate(f, 1):
                    self.stats['procedures']['total'] += 1
                    
                    if not line.strip():
                        continue
                    
                    data = self.parse_procedimento_line(line)
                    
                    if not data or not data.get('code'):
                        self.stats['procedures']['errors'] += 1
                        self.stats['error_messages'].append(f"Procedimento linha {line_num}: Dados inválidos")
                        continue
                    
                    imported_codes.add(data['code'])
                    procedure = Procedure.query.filter_by(code=data['code']).first()
                    
                    try:
                        if procedure:
                            for key, value in data.items():
                                if key != 'code':
                                    setattr(procedure, key, value)
                            procedure.is_active = True
                            self.stats['procedures']['updated'] += 1
                        else:
                            procedure = Procedure(
                                code=data['code'],
                                description=data['description'],
                                complexity_type=data.get('complexity_type'),
                                gender_type=data.get('gender_type'),
                                max_execution_qty=data.get('qt_maxima_execucao'),
                                permanence_days=data.get('qt_dias_permanencia'),
                                points=data.get('qt_pontos'),
                                min_age=data.get('vl_idade_minima'),
                                max_age=data.get('vl_idade_maxima'),
                                value_sh=data.get('vl_sh'),
                                value_sa=data.get('vl_sa'),
                                value_sp=data.get('vl_sp'),
                                financing_code=data.get('financing_code'),
                                rubric_code=data.get('rubric_code'),
                                permanence_time=data.get('qt_tempo_permanencia'),
                                competence_date=data.get('competence_date'),
                                is_active=True
                            )
                            db.session.add(procedure)
                            self.stats['procedures']['inserted'] += 1
                        
                        if (self.stats['procedures']['inserted'] + self.stats['procedures']['updated']) % 100 == 0:
                            db.session.commit()
                            logger.info(f"Procedimentos processados: {self.stats['procedures']['inserted'] + self.stats['procedures']['updated']}")
                    
                    except Exception as e:
                        self.stats['procedures']['errors'] += 1
                        error_msg = f"Procedimento linha {line_num} (Código: {data['code']}): {str(e)}"
                        self.stats['error_messages'].append(error_msg)
                        logger.error(error_msg)
                        db.session.rollback()
            
            codes_to_deactivate = existing_codes - imported_codes
            if codes_to_deactivate:
                Procedure.query.filter(Procedure.code.in_(codes_to_deactivate)).update(
                    {'is_active': False}, 
                    synchronize_session=False
                )
                self.stats['procedures']['deactivated'] = len(codes_to_deactivate)
            
            db.session.commit()
            logger.info(f"Importação de procedimentos concluída")
            return self.stats
        
        except Exception as e:
            db.session.rollback()
            error_msg = f"Erro fatal na importação de procedimentos: {str(e)}"
            logger.error(error_msg)
            self.stats['error_messages'].append(error_msg)
            raise
    
    def import_cids_from_file(self, file_path: str, encoding: str = 'latin-1') -> Dict:
        logger.info(f"Iniciando importação de CIDs: {file_path}")
        
        existing_codes = {c.code for c in Cid.query.with_entities(Cid.code).all()}
        imported_codes = set()
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                for line_num, line in enumerate(f, 1):
                    self.stats['cids']['total'] += 1
                    
                    if not line.strip():
                        continue
                    
                    data = self.parse_cid_line(line)
                    
                    if not data or not data.get('code'):
                        self.stats['cids']['errors'] += 1
                        self.stats['error_messages'].append(f"CID linha {line_num}: Dados inválidos")
                        continue
                    
                    imported_codes.add(data['code'])
                    cid = Cid.query.filter_by(code=data['code']).first()
                    
                    try:
                        if cid:
                            cid.description = data['description']
                            cid.is_active = True
                            self.stats['cids']['updated'] += 1
                        else:
                            cid = Cid(
                                code=data['code'],
                                description=data['description'],
                                is_active=True
                            )
                            db.session.add(cid)
                            self.stats['cids']['inserted'] += 1
                        
                        if (self.stats['cids']['inserted'] + self.stats['cids']['updated']) % 100 == 0:
                            db.session.commit()
                            logger.info(f"CIDs processados: {self.stats['cids']['inserted'] + self.stats['cids']['updated']}")
                    
                    except Exception as e:
                        self.stats['cids']['errors'] += 1
                        error_msg = f"CID linha {line_num} (Código: {data['code']}): {str(e)}"
                        self.stats['error_messages'].append(error_msg)
                        logger.error(error_msg)
                        db.session.rollback()
            
            codes_to_deactivate = existing_codes - imported_codes
            if codes_to_deactivate:
                Cid.query.filter(Cid.code.in_(codes_to_deactivate)).update(
                    {'is_active': False}, 
                    synchronize_session=False
                )
                self.stats['cids']['deactivated'] = len(codes_to_deactivate)
            
            db.session.commit()
            logger.info(f"Importação de CIDs concluída")
            return self.stats
        
        except Exception as e:
            db.session.rollback()
            error_msg = f"Erro fatal na importação de CIDs: {str(e)}"
            logger.error(error_msg)
            self.stats['error_messages'].append(error_msg)
            raise
    
    def import_relationships_from_file(self, file_path: str, encoding: str = 'latin-1') -> Dict:
        logger.info(f"Iniciando importação de relacionamentos: {file_path}")
        
        ProcedureCid.query.delete()
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                for line_num, line in enumerate(f, 1):
                    self.stats['relationships']['total'] += 1
                    
                    if not line.strip():
                        continue
                    
                    data = self.parse_procedimento_cid_line(line)
                    
                    if not data or not data.get('procedure_code') or not data.get('cid_code'):
                        self.stats['relationships']['errors'] += 1
                        continue
                    
                    try:
                        rel = ProcedureCid(
                            procedure_code=data['procedure_code'],
                            cid_code=data['cid_code']
                        )
                        db.session.add(rel)
                        self.stats['relationships']['inserted'] += 1
                        
                        if self.stats['relationships']['inserted'] % 100 == 0:
                            db.session.commit()
                            logger.info(f"Relacionamentos processados: {self.stats['relationships']['inserted']}")
                    
                    except Exception as e:
                        self.stats['relationships']['errors'] += 1
                        db.session.rollback()
            
            db.session.commit()
            logger.info(f"Importação de relacionamentos concluída")
            return self.stats
        
        except Exception as e:
            db.session.rollback()
            error_msg = f"Erro fatal na importação de relacionamentos: {str(e)}"
            logger.error(error_msg)
            self.stats['error_messages'].append(error_msg)
            raise
    
    def import_from_zip(self, zip_path: str) -> Dict:
        temp_dir = None
        
        try:
            files = self.extract_zip(zip_path)
            temp_dir = files.get('temp_dir')
            
            if 'procedimento' in files:
                self.import_procedures_from_file(files['procedimento'])
            
            if 'cid' in files:
                self.import_cids_from_file(files['cid'])
            
            if 'procedimento_cid' in files:
                self.import_relationships_from_file(files['procedimento_cid'])
            
            return self.stats
        
        finally:
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)


from decimal import InvalidOperation
