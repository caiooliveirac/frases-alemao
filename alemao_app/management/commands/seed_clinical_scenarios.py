import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from alemao_app.models import CEFRLevel, ClinicalScenario
from .c1_scenarios import C1_SCENARIOS


A1_SCENARIOS = [
    "Guten Morgen. Ich bin die Ärztin auf dieser Station. Wie ist Ihr Name?",
    "Kommen Sie bitte herein und setzen Sie sich. Was kann ich für Sie tun? Haben Sie Schmerzen?",
    "Wo genau tut es weh? Zeigen Sie mir das bitte. Ist der Schmerz sehr stark?",
    "Machen Sie bitte den Oberkörper frei. Ich muss Sie untersuchen. Atmen Sie tief ein.",
    "Haben Sie heute schon Tabletten genommen? Welche Medikamente nehmen Sie? Geben Sie mir bitte die Liste.",
    "Sie haben ein bisschen Fieber. Das ist nicht so schlimm. Trinken Sie bitte viel Tee und Wasser.",
    "Bitte legen Sie sich auf die Liege. Ich mache jetzt einen Ultraschall. Es ist ein bisschen kalt.",
    "Wie alt sind Sie? Wie groß und wie schwer sind Sie? Stellen Sie sich bitte auf die Waage.",
    "Haben Sie Allergien gegen Medikamente? Sind Sie allergisch gegen Penicillin? Das ist sehr wichtig.",
    "Sie dürfen jetzt nichts essen und trinken. Wir müssen Ihr Blut untersuchen. Die Schwester kommt gleich.",
    "Öffnen Sie bitte den Mund ganz weit. Sagen Sie einmal 'Ah'. Ihr Hals ist rot und entzündet.",
    "Sie brauchen viel Ruhe. Bleiben Sie heute und morgen im Bett. Gehen Sie nicht zur Arbeit.",
    "Hier ist Ihr Rezept für die Apotheke. Nehmen Sie eine Tablette am Morgen. Nehmen Sie eine Tablette am Abend.",
    "Wie geht es Ihnen heute? Haben Sie gut geschlafen? Sind die Schmerzen schon besser?",
    "Wir müssen ein Röntgenbild machen. Gehen Sie bitte den Flur entlang. Der Warteraum ist auf der rechten Seite.",
    "Haben Sie Übelkeit oder müssen Sie erbrechen? Haben Sie auch Durchfall? Seit wann haben Sie das?",
    "Haben Sie keine Angst, bitte. Die Untersuchung dauert nur fünf Minuten. Es tut wirklich nicht weh.",
    "Können Sie den Arm bewegen? Heben Sie bitte das rechte Bein. Tut das weh, wenn ich hier drücke?",
    "Die Blutwerte sind alle normal. Ihr Blutdruck ist auch gut. Sie sind gesund und können nach Hause gehen.",
    "Brauchen Sie eine Krankmeldung für den Arbeitgeber? Ich schreibe Sie für drei Tage krank. Gute Besserung!",
    "Bitte husten Sie einmal stark. Atmen Sie jetzt ganz normal weiter. Die Lunge ist frei.",
    "Der Chefarzt kommt später zur Visite. Er spricht dann mit Ihnen. Haben Sie noch Fragen?",
    "Bitte drehen Sie sich auf die linke Seite. Machen Sie den Rücken ganz rund. Bleiben Sie ganz ruhig liegen.",
    "Guten Tag, ich bin Thais. Ich arbeite hier als Ärztin. Sprechen Sie Deutsch oder Englisch?",
    "Haben Sie Probleme mit dem Magen? Ist Ihnen oft schlecht nach dem Essen? Bitte beschreiben Sie das genau.",
    "Sie müssen im Krankenhaus bleiben. Wir machen morgen noch ein paar Tests. Ihre Familie kann Sie am Nachmittag besuchen.",
    "Bitte geben Sie mir Ihren Arm. Ich messe jetzt den Blutdruck. Ihr Puls ist ein bisschen schnell.",
    "Können Sie bitte aufstehen? Gehen Sie ein paar Schritte nach vorne. Drehen Sie sich wieder um.",
    "Haben Sie Fieber zu Hause gemessen? Wie hoch war das Fieber? Haben Sie Schüttelfrost?",
    "Ich verstehe Sie leider nicht so gut. Sprechen Sie bitte langsam. Wo genau ist das Problem?",
    "Wie lange haben Sie schon Schmerzen? Seit gestern Abend? Nehmen Sie bitte Platz.",
    "Zeigen Sie mir Ihren Fuß. Der Fuß ist dick und blau. Können Sie gehen?",
    "Hier ist Ihre Tablette für die Nacht. Trinken Sie ein Glas Wasser dazu. Schlafen Sie gut.",
    "Wann sind Sie geboren? Wo wohnen Sie genau? Haben Sie Ihre Versichertenkarte dabei?",
    "Ihr Baby weint heute sehr viel. Hat es Bauchschmerzen? Hat es heute schon Milch getrunken?",
    "Sie können morgen nach Hause gehen. Kommen Sie am Freitag zur Kontrolle. Vergessen Sie das Rezept nicht.",
    "Wie stark sind die Schmerzen von eins bis zehn? Sind sie sehr schlimm? Ich gebe Ihnen eine Schmerztablette.",
    "Die Toilette ist gleich hier links. Das Röntgen ist im ersten Stock. Gehen Sie bitte dorthin.",
    "Sie dürfen heute vor der Operation noch nichts essen. Morgen früh bekommen Sie Frühstück. Haben Sie großen Hunger?",
    "Stehen Sie bitte nicht alleine auf. Klingeln Sie, wenn Sie Hilfe brauchen. Wir helfen Ihnen gerne.",
    "Atmen Sie ganz tief durch den Mund ein. Und jetzt wieder aus. Sehr gut, machen Sie das noch einmal.",
    "Die Wunde am Bein ist sehr klein. Ich mache Ihnen einen neuen Verband. Bitte heute nicht duschen.",
    "Der Blutdruck ist heute viel besser. Er ist nicht mehr zu hoch. Nehmen Sie Ihre Medikamente normal weiter.",
    "Ist das Ihre Frau auf dem Stuhl? Sie kann gerne hierbleiben. Die Besuchszeit ist bis 20 Uhr.",
    "Verstehen Sie mich gut? Ich kann das gerne noch einmal sagen. Spreche ich vielleicht zu schnell?",
    "Wir müssen jetzt etwas schnell machen. Der Arzt kommt sofort zu Ihnen. Bitte bleiben Sie ganz ruhig.",
    "Schauen Sie bitte auf meinen Finger. Folgen Sie dem Finger nur mit den Augen. Haben Sie oft Kopfschmerzen?",
    "Wann waren Sie das letzte Mal auf der Toilette? War der Stuhl normal? Haben Sie Schmerzen beim Wasserlassen?",
    "Sind Sie heute sehr müde? Sie müssen sich gut ausruhen. Dieses Zimmer ist schön ruhig.",
    "Was ist genau passiert? Sind Sie mit dem Auto gefahren? Haben Sie sich den Kopf gestoßen?",
    "Ist Ihnen kalt? Brauchen Sie vielleicht noch eine warme Decke? Ich hole Ihnen sofort eine.",
    "Sind Sie heute nüchtern? Haben Sie heute Morgen Kaffee getrunken? Wirklich auch kein Wasser?",
    "Sie bekommen jetzt einen Gips. Der Gips muss sechs Wochen bleiben. Laufen Sie bitte nur mit den Krücken.",
    "Haben Sie sich heute schon übergeben? Wie oft war das heute? Hier ist eine kleine Schale für Sie.",
    "Das tut mir wirklich leid. Das wird bald wieder gut, keine Sorge. Sie sind hier bei uns in guten Händen.",
    "Ich nehme Ihnen jetzt etwas Blut ab. Machen Sie bitte eine feste Faust. Es piekst nur ein kleines bisschen.",
    "Drücken Sie einfach diesen roten Knopf. Dann kommt sofort die Krankenschwester. Machen Sie das auch in der Nacht.",
    "Sie haben leider Diabetes. Sie dürfen jetzt keinen Zucker mehr essen. Dieser Tee ist ohne Zucker.",
    "Bitte ziehen Sie sich jetzt wieder an. Ihre Kleidung liegt dort auf dem Stuhl. Der Arztbrief ist schon fertig.",
    "Auf Wiedersehen, Herr Schmidt. Bleiben Sie gesund und ruhen Sie sich aus. Die Papiere sind vorne an der Rezeption.",
]


B1_SCENARIOS = [
    "Der Patient sagt, dass er seit drei Tagen starke Kopfschmerzen hat.",
    "Frau Weber hat Fieber und hustet viel, deshalb bleibt sie im Bett.",
    "Als der Patient gestern Abend gestürzt ist, hat er sich das Bein gebrochen.",
    "Haben Sie Schmerzen, wenn Sie tief einatmen?",
    "Der Mann, der heute Morgen gekommen ist, hat Probleme mit dem Magen.",
    "Wir müssen wissen, ob Sie Medikamente gegen hohen Blutdruck nehmen.",
    "Der Patient konnte nicht schlafen, weil die Schmerzen zu stark waren.",
    "Seit wann haben Sie diese roten Flecken auf der Haut?",
    "Sie müssen mir sagen, wenn Ihnen plötzlich schwindelig wird.",
    "Der Arzt hat gefragt, wo genau der Schmerz anfängt.",
    "Herr Müller ist Diabetiker und muss regelmäßig seinen Blutzucker messen.",
    "Ich habe den Patienten gefragt, ob er schon einmal operiert wurde.",
    "Das ist die Patientin, deren Arm gestern geröntgt wurde.",
    "Wenn das Fieber nicht sinkt, müssen wir Ihnen ein anderes Medikament geben.",
    "Bitte zeigen Sie mir, wo es am meisten wehtut.",
    "Hatten Sie schon einmal Probleme mit dem Herzen oder der Lunge?",
    "Der Patient atmet sehr schnell und hat Schweiß auf der Stirn.",
    "Weil ihm übel war, hat er heute noch nichts gegessen.",
    "Haben Sie in der letzten Zeit ungewollt an Gewicht verloren?",
    "Der Schmerz strahlt in den linken Arm und in den Rücken aus.",
    "Als das Kind Fieber bekam, sind die Eltern sofort ins Krankenhaus gefahren.",
    "Die Frau sagt, dass sie allergisch gegen Pflaster und Jod ist.",
    "Bevor Sie ins Krankenhaus kamen, haben Sie da Schmerzmittel genommen?",
    "Er hat sich den Fuß verstaucht, als er die Treppe hinuntergegangen ist.",
    "Trinken Sie Alkohol oder rauchen Sie Zigaretten?",
    "Der Patient beschwert sich über ein Stechen in der Brust.",
    "Wir müssen abklären, warum Sie immer so müde sind.",
    "Wie oft müssen Sie nachts aufstehen, um auf die Toilette zu gehen?",
    "Das Gelenk ist geschwollen und rot, weil es entzündet ist.",
    "Ich verstehe nicht genau, was Sie meinen. Können Sie das erklären?",
    "Die Krankenschwester hat ihm heute Morgen schon Blut abgenommen.",
    "Wir machen jetzt ein EKG, damit wir Ihr Herz überprüfen können.",
    "Der Arzt kommt gleich, um den Ultraschall zu machen.",
    "Bitte ziehen Sie Ihr Hemd aus und legen Sie sich auf die Liege.",
    "Der Befund aus dem Labor ist leider noch nicht da.",
    "Gestern wurde bei Herrn Klein eine Magenspiegelung gemacht.",
    "Sie dürfen vor der Operation morgen früh nichts essen und nichts trinken.",
    "Die Schwester bringt Ihnen gleich die Tabletten für den Abend.",
    "Wir bringen den Patienten jetzt in den OP-Saal.",
    "Nachdem er aufgewacht war, hat er sofort nach Wasser gefragt.",
    "Das Röntgenbild zeigt, dass der Knochen gebrochen ist.",
    "Ich muss Ihren Blutdruck und Ihren Puls messen.",
    "Die Visite beginnt heute um acht Uhr mit dem Chefarzt.",
    "Können Sie bitte den Arm ganz locker lassen?",
    "Wir haben einen neuen Patienten auf Station 4, der isoliert werden muss.",
    "Der Transportdienst holt Frau Schmidt jetzt zum CT ab.",
    "Sie müssen diesen Becher für die Urinprobe auf der Toilette füllen.",
    "Die Infusion läuft zu langsam, ich muss sie etwas schneller einstellen.",
    "Wenn die Flasche leer ist, klingeln Sie bitte nach der Schwester.",
    "Der Verband muss jeden Tag gewechselt werden, weil die Wunde nässt.",
    "Ich schreibe Ihnen ein Rezept für die Apotheke auf.",
    "Die Ergebnisse der Blutuntersuchung bespreche ich später mit Ihnen.",
    "Der Arzt hat den Patienten untersucht und ihm ein Medikament verschrieben.",
    "Weil die Schmerzen so stark waren, hat sie eine Spritze bekommen.",
    "Bitte atmen Sie tief ein und halten Sie die Luft kurz an.",
    "Die Wunde sieht gut aus, es gibt keine Anzeichen für eine Infektion.",
    "Wir müssen den Blutzucker vor jedem Essen kontrollieren.",
    "Das Bett Nummer 3 ist frei und wurde bereits frisch gemacht.",
    "Der Kollege hat die Akte des Patienten noch nicht gefunden.",
    "Gestern Abend hatte er leichtes Fieber, aber heute ist die Temperatur normal.",
    "Frau Bauer, Sie können morgen wahrscheinlich nach Hause gehen.",
    "Nehmen Sie diese Tablette immer eine halbe Stunde vor dem Frühstück.",
    "Wenn Sie Kopfschmerzen bekommen, dürfen Sie Paracetamol nehmen.",
    "Sie müssen viel Wasser trinken, mindestens zwei Liter am Tag.",
    "Der Arzt sagt, dass Sie sich noch ein paar Tage ausruhen müssen.",
    "Falls es schlimmer wird, müssen Sie sofort wieder zu uns kommen.",
    "Mit diesem Rezept können Sie die Medikamente in der Apotheke holen.",
    "Wir geben Ihnen einen Brief für Ihren Hausarzt mit.",
    "Bitte belasten Sie das Bein nicht und benutzen Sie die Krücken.",
    "Sie dürfen für die nächsten sechs Wochen keinen Sport machen.",
    "Die Fäden können in zehn Tagen vom Hausarzt gezogen werden.",
    "Vergessen Sie nicht, den Termin für die Kontrolle nächste Woche zu machen.",
    "Wenn Ihnen schlecht ist, rufen Sie mich bitte sofort.",
    "Das ist ganz normal nach so einer Operation, machen Sie sich keine Sorgen.",
    "Sie sollten versuchen, jeden Tag ein bisschen spazieren zu gehen.",
    "Bitte unterschreiben Sie hier, dass Sie mit der Behandlung einverstanden sind.",
    "Ich erkläre Ihnen jetzt, wie Sie das Insulin selbst spritzen können.",
    "Achten Sie darauf, dass der Verband beim Duschen nicht nass wird.",
    "Essen Sie in den nächsten Tagen nur leichte Kost, zum Beispiel Suppe.",
    "Rufen Sie den Notarzt, wenn Sie wieder diesen Druck in der Brust spüren.",
    "Ich zeige Ihnen eine Übung, die Sie jeden Morgen im Bett machen können.",
    "Das Medikament kann Sie müde machen, deshalb dürfen Sie nicht Auto fahren.",
    "Wir freuen uns, dass Sie so schnell wieder gesund geworden sind.",
    "Wenn Sie Hilfe beim Anziehen brauchen, sagen Sie uns einfach Bescheid.",
    "Haben Sie noch Fragen an den Arzt, bevor er geht?",
    "Der Physiotherapeut kommt am Nachmittag zu Ihnen ans Bett.",
    "Trinken Sie keinen Kaffee und keinen Alkohol, solange Sie die Tabletten nehmen.",
    "Ihr Zustand hat sich so sehr verbessert, dass Sie keine Infusion mehr brauchen.",
    "Bitte bleiben Sie heute noch im Bett, Sie sind noch etwas schwach.",
    "Melden Sie sich sofort, wenn Sie wieder Blut im Urin bemerken.",
]


class Command(BaseCommand):
    help = "Popula cenários clínicos A1/B1/C1 na tabela clinical_scenarios"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga cenários existentes antes de importar novamente.",
        )

    def handle(self, *args, **options):
        app_file = Path(__file__).resolve().parents[3] / "frontend" / "src" / "App.jsx"
        if not app_file.exists():
            raise CommandError(f"Arquivo não encontrado: {app_file}")

        content = app_file.read_text(encoding="utf-8")

        block_match = re.search(r"const\s+CLINICAL_SCENARIOS\s*=\s*\[(.*?)\];", content, flags=re.S)
        c1_scenarios = []
        if block_match:
            array_block = block_match.group(1)
            entries = re.findall(r'"((?:[^"\\]|\\.)*)"\s*,?', array_block)
            c1_scenarios = [entry.replace(r"\n", "\n").strip() for entry in entries if entry.strip()]

        if not c1_scenarios and not options.get("reset"):
            c1_scenarios = list(
                ClinicalScenario.objects.filter(proficiency_level=CEFRLevel.C1).values_list("text", flat=True)
            )

        if not c1_scenarios:
            c1_scenarios = C1_SCENARIOS

        if not c1_scenarios:
            raise CommandError("Nenhum cenário C1 encontrado para importar.")

        if options.get("reset"):
            ClinicalScenario.objects.all().delete()

        created_count = 0

        for text in c1_scenarios:
            _, created = ClinicalScenario.objects.get_or_create(
                text=text,
                defaults={"is_active": True, "proficiency_level": CEFRLevel.C1},
            )
            if created:
                created_count += 1

        for text in B1_SCENARIOS:
            _, created = ClinicalScenario.objects.get_or_create(
                text=text,
                defaults={"is_active": True, "proficiency_level": CEFRLevel.B1},
            )
            if created:
                created_count += 1

        for text in A1_SCENARIOS:
            _, created = ClinicalScenario.objects.get_or_create(
                text=text,
                defaults={"is_active": True, "proficiency_level": CEFRLevel.A1},
            )
            if created:
                created_count += 1

        total = ClinicalScenario.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed concluído. C1: {len(c1_scenarios)} | B1: {len(B1_SCENARIOS)} | A1: {len(A1_SCENARIOS)} | Novos: {created_count} | Total: {total}"
            )
        )
