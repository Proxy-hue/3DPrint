from django.http import FileResponse
from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import PrintModel
from .serializers import PrintModelSerializer


class PrintModelListCreateView(generics.ListCreateAPIView):
    serializer_class = PrintModelSerializer

    def get_queryset(self):
        return PrintModel.objects.filter(owner=self.request.user)


class PrintModelDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = PrintModelSerializer

    def get_queryset(self):
        return PrintModel.objects.filter(owner=self.request.user)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def download_model(request, pk):
    model = PrintModel.objects.filter(pk=pk, owner=request.user).first()
    if model is None:
        return Response({"detail": "Модель не найдена."}, status=404)
    model.file.open("rb")
    response = FileResponse(model.file, as_attachment=True, filename=model.original_name)
    response["Content-Length"] = model.size
    return response
