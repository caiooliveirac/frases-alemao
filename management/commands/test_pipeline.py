import spacy
from django.core.management.base import BaseCommand, CommandError

from ...models import TextDocument, TextTokenRelation
from ...text_processing_service import TextDissector, TextDissectorError


class Command(BaseCommand):
    help = "Executa um teste de fogo do pipeline NLP com frase médica em alemão."

    def handle(self, *args, **options):
        sentence = "Der Notarzt verabreicht dem Patienten intravenös das starke Schmerzmittel."

        try:
            document_id = TextDissector(raw_text=sentence, title="Teste de emergência médica").process_and_persist()
        except TextDissectorError as exc:
            raise CommandError(f"Falha no TextDissector: {exc}") from exc

        try:
            document = TextDocument.objects.get(id=document_id)
        except TextDocument.DoesNotExist as exc:
            raise CommandError("Documento processado não foi encontrado no banco.") from exc

        relations = list(
            TextTokenRelation.objects.select_related("word_token")
            .filter(text_document_id=document.id)
            .order_by("position")
        )

        nlp = spacy.load("de_core_news_lg")
        doc = nlp(document.raw_text)
        surface_by_position = {token.i: token.text for token in doc}

        self.stdout.write(self.style.SUCCESS(f"Documento criado com ID: {document.id}"))
        self.stdout.write("Resultado da dissecação:")
        self.stdout.write("-" * 80)

        for relation in relations:
            surface = surface_by_position.get(relation.position, "?")
            lemma = relation.word_token.lemma
            gram_case = relation.grammatical_case
            self.stdout.write(
                f"pos={relation.position:>2} | palavra={surface:<18} | lema={lemma:<18} | caso={gram_case}"
            )

        self.stdout.write("-" * 80)
        self.stdout.write(self.style.SUCCESS("Teste de fogo concluído."))
