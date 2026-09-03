import json

from django.core.management.base import BaseCommand

from ...services.data_audit import audit_model_data


class Command(BaseCommand):
    help = "Audita conflictos de datos antes de activar restricciones nuevas."

    def handle(self, *args, **options):
        report = audit_model_data()
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        if any(report.values()):
            self.stdout.write(self.style.WARNING("La auditoría ha encontrado datos pendientes."))
        else:
            self.stdout.write(self.style.SUCCESS("La auditoría no ha encontrado conflictos."))
