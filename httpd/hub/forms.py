from django import forms

class EPANETUploadFileForm(forms.Form):
    epanet_model_name = forms.CharField(max_length=64)
    epanet_file = forms.FileField()

