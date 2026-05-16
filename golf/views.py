from django.shortcuts import render

def dashboard(request):
    holes = range(1, 19)

    return render(request, "golf/dashboard.html", {
        "holes": holes,
    })