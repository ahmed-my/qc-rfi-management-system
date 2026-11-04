from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import RFI, UserProfile, Assignment, Inspection, PunchList, PunchItem


class LoginForm(AuthenticationForm):
    """
    Login form for the QC RFI Management System.
    """

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autocomplete": "username",
            }
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        )
    )


class QCUserCreationForm(forms.Form):
    """
    Create a Django user together with their QC profile.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First name",
            }
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last name",
            }
        ),
    )

    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autocomplete": "off",
            }
        ),
    )

    password = forms.CharField(
        min_length=8,
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "new-password",
            }
        ),
    )

    password_confirm = forms.CharField(
        min_length=8,
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm password",
                "autocomplete": "new-password",
            }
        ),
    )

    role = forms.ChoiceField(
        choices=[
            (
                UserProfile.Role.SUPERVISOR,
                UserProfile.Role.SUPERVISOR.label,
            ),
            (
                UserProfile.Role.INSPECTOR,
                UserProfile.Role.INSPECTOR.label,
            ),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    is_active_qc = forms.BooleanField(
        required=False,
        initial=True,
        label="QC access active",
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "A user with this username already exists."
            )

        return username

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error(
                "password_confirm",
                "The passwords do not match.",
            )

        return cleaned_data


class QCUserEditForm(forms.Form):
    """
    Edit an existing QC user's information and role.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First name",
            }
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last name",
            }
        ),
    )

    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
            }
        ),
    )

    role = forms.ChoiceField(
        choices=[
            (
                UserProfile.Role.ADMIN,
                UserProfile.Role.ADMIN.label,
            ),
            (
                UserProfile.Role.SUPERVISOR,
                UserProfile.Role.SUPERVISOR.label,
            ),
            (
                UserProfile.Role.INSPECTOR,
                UserProfile.Role.INSPECTOR.label,
            ),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    is_active_qc = forms.BooleanField(
        required=False,
        label="QC access active",
    )

    def __init__(self, *args, user_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_instance = user_instance

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        queryset = User.objects.filter(
            username__iexact=username
        )

        if self.user_instance:
            queryset = queryset.exclude(
                pk=self.user_instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "A user with this username already exists."
            )

        return username


class QCSetPasswordForm(SetPasswordForm):
    """
    Administrator form for changing another user's password.
    """

    new_password1 = forms.CharField(
        label="New password",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password",
                "autocomplete": "new-password",
            }
        ),
    )

    new_password2 = forms.CharField(
        label="Confirm new password",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
    )

class RFIRegistrationForm(forms.ModelForm):
    """
    Form used by QC supervisors to register a newly received RFI.
    """

    class Meta:
        model = RFI

        fields = [
            "rfi_number",
            "revision",
            "certificate_code",
            "client_rfi_number",
            "contractor",
            "date_received",
            "original_planned_start",
            "original_planned_end",
            "planned_time",
            "discipline",
            "area",
            "unit",
            "system",
            "subsystem",
            "qc_code",
            "itp_document",
            "form_code",
            "iwp_code",
            "inspection_activity",
            "reference_documents",
        ]

        widgets = {
            "rfi_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "RFI number",
                }
            ),

            "revision": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Revision",
                }
            ),

            "certificate_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Certificate code",
                }
            ),

            "client_rfi_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Client RFI number",
                }
            ),

            "contractor": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Contractor",
                }
            ),

            "date_received": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "original_planned_start": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "original_planned_end": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "planned_time": forms.TimeInput(
                attrs={
                    "class": "form-control",
                    "type": "time",
                }
            ),

            "discipline": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Discipline",
                }
            ),

            "area": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Area",
                }
            ),

            "unit": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Unit",
                }
            ),

            "system": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "System",
                }
            ),

            "subsystem": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Subsystem",
                }
            ),

            "qc_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "QC code",
                }
            ),

            "itp_document": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ITP document",
                }
            ),

            "form_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Form code",
                }
            ),

            "iwp_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "IWP code",
                }
            ),

            "inspection_activity": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Inspection activity",
                }
            ),

            "reference_documents": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Reference documents",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Daewoo is the current project contractor.
        self.fields["contractor"].initial = "Daewoo"

        # These are the dates that should normally be provided
        # during RFI registration.
        self.fields["date_received"].required = True

        self.fields["original_planned_start"].required = True
        self.fields["original_planned_end"].required = True

        # Optional technical/reference fields.
        optional_fields = [
            "revision",
            "certificate_code",
            "client_rfi_number",
            "planned_time",
            "discipline",
            "area",
            "unit",
            "system",
            "subsystem",
            "qc_code",
            "itp_document",
            "form_code",
            "iwp_code",
            "inspection_activity",
            "reference_documents",
        ]

        for field_name in optional_fields:
            self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()

        planned_start = cleaned_data.get("original_planned_start")
        planned_end = cleaned_data.get("original_planned_end")

        if planned_start and planned_end:
            if planned_end < planned_start:
                self.add_error(
                    "original_planned_end",
                    "The planned end date cannot be before the planned start date."
                )

        return cleaned_data

class RFIAssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["inspector", "reason"]
        widgets = {
            "inspector": forms.Select(
                attrs={"class": "form-control"}
            ),
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional assignment note or reason",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        inspectors = (
            UserProfile.objects
            .filter(
                role=UserProfile.Role.INSPECTOR,
                is_active_qc=True,
                user__is_active=True,
            )
            .select_related("user")
            .order_by(
                "user__first_name",
                "user__last_name",
                "user__username",
            )
        )

        self.fields["inspector"].choices = [
            (
                profile.user.id,
                profile.user.get_full_name()
                or profile.user.username,
            )
            for profile in inspectors
        ]

        self.fields["inspector"].label = "QC Inspector"


class StartInspectionForm(forms.Form):
    inspection_date = forms.DateField(
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
        label="Inspection Date",
    )

    start_time = forms.TimeField(
        widget=forms.TimeInput(
            attrs={
                "class": "form-control",
                "type": "time",
            }
        ),
        label="Start Time",
    )

    def __init__(self, *args, rfi=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.rfi = rfi

    def clean_inspection_date(self):
        inspection_date = self.cleaned_data["inspection_date"]

        if self.rfi is None:
            raise forms.ValidationError(
                "The RFI could not be determined."
            )

        if inspection_date < self.rfi.current_planned_start:
            raise forms.ValidationError(
                (
                    "The inspection date cannot be before the "
                    "current Inspection Planned Period."
                )
            )

        if inspection_date > self.rfi.current_planned_end:
            raise forms.ValidationError(
                (
                    "The inspection date is outside the current "
                    "Inspection Planned Period. The RFI has expired "
                    "for inspection and must be renewed by the supervisor."
                )
            )

        return inspection_date


class RFIRenewalForm(forms.Form):
    new_start = forms.DateField(
        label="New Planned Start Date",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control",
        }),
    )

    new_end = forms.DateField(
        label="New Planned End Date",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control",
        }),
    )

    reason = forms.CharField(
        label="Reason for Renewal",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "Explain why the inspection period needs renewal.",
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_start = cleaned_data.get("new_start")
        new_end = cleaned_data.get("new_end")

        if new_start and new_end and new_end < new_start:
            self.add_error(
                "new_end",
                "The planned end date cannot be before the start date."
            )

        return cleaned_data


class ReturnToSupervisorForm(forms.Form):
    reason = forms.CharField(
        label="Reason for Returning to Supervisor",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "Explain why this RFI is being returned to the supervisor.",
        }),
    )


class InspectionForm(forms.ModelForm):

    class Meta:
        model = Inspection

        fields = [
            "inspection_date",
            "start_time",
            "overall_result",
            "remarks",
        ]

        widgets = {
            "inspection_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "type": "time",
                    "class": "form-control",
                }
            ),
            "overall_result": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Enter inspection remarks",
                }
            ),
        }

        labels = {
            "inspection_date": "Inspection Date",
            "start_time": "Start Time",
            "overall_result": "Inspection Result",
            "remarks": "Remarks",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["inspection_date"].required = True
        self.fields["start_time"].required = True
        self.fields["overall_result"].required = True
        self.fields["remarks"].required = False

        if self.instance and self.instance.pk:
            self.fields["inspection_date"].disabled = True
            self.fields["start_time"].disabled = True


class PunchListCreateForm(forms.ModelForm):
    class Meta:
        model = PunchList
        fields = ["punch_list_number", "date_created", "remarks"]
        widgets = {
            "punch_list_number": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Optional — leave blank to generate automatically",
            }),
            "date_created": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "remarks": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Enter punch list remarks",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["punch_list_number"].required = False
        self.fields["date_created"].initial = timezone.localdate()


class PunchItemCreateForm(forms.ModelForm):

    class Meta:
        model = PunchItem
        fields = [
            "item_number",
            "item_tag",
            "description",
            "category",
            "action",
            "responsible_party",
            "target_date",
        ]

        widgets = {
            "item_number": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "item_tag": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Item tag (optional)",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Describe the outstanding item",
                }
            ),
            "category": forms.Select(
                attrs={"class": "form-control"}
            ),
            "action": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Required corrective action",
                }
            ),
            "responsible_party": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Responsible party",
                }
            ),
            "target_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }
