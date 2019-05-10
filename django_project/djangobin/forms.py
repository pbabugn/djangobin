from django import forms
from django.core.exceptions import ValidationError
from .models import Snippet, Language, Author, Tag
from .utils import Preference as Pref, get_current_user
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail


class SnippetForm(forms.ModelForm):
    snippet_tags = forms.CharField(required=False,
                           widget=forms.TextInput(attrs={
                               'class': 'selectpicker form-control',
                               'placeholder': 'Enter tags (optional)'
                            }))

    class Meta:
        model = Snippet
        fields = ('original_code', 'language', 'expiration', 'exposure', 'title', )
        widgets = {
            'original_code': forms.Textarea(attrs={'class': 'form-control', 'rows': '10',
                                                   'spellcheck': 'false'}),
            'language': forms.Select(attrs={'class': 'selectpicker foo form-control',
                                            'data-live-search': 'true',
                                            'data-size': '5'}),
            'expiration': forms.Select(attrs={'class': 'selectpicker form-control'}),
            'exposure': forms.Select(attrs={'class': 'selectpicker form-control'}),
            'title': forms.TextInput(attrs={'class': 'selectpicker form-control',
                                            'placeholder': 'Enter Title (optional)'}),
        }

    def __init__(self, request, *args, **kwargs):
        super(SnippetForm, self).__init__(*args, **kwargs)

        if request.user.is_authenticated:
            self.fields['exposure'].choices = Pref.exposure_choices
            self.initial = request.user.profile.get_preferences()
        else:
            self.fields['exposure'].choices = \
                [(k, v) for k, v in Pref.exposure_choices if k != 'private']

            l = Language.objects.get(name='Plain Text')
            self.initial = {'language': l.id, 'exposure': 'public', 'expiration': 'never'}

    def save(self, request):
        # get the Snippet object, without saving it into the database
        snippet = super(SnippetForm, self).save(commit=False)
        snippet.user = get_current_user(request)
        snippet.save()
        tag_list = [tag.strip().lower()
                    for tag in self.cleaned_data['snippet_tags'].split(',') if tag]
        if len(tag_list) > 0:
            for tag in tag_list:
                t = Tag.objects.get_or_create(name=tag)
                snippet.tags.add(t[0])
        return snippet


class ContactForm(forms.Form):
    BUG = 'b'
    FEEDBACK = 'fb'
    NEW_FEATURE = 'nf'
    OTHER = 'o'
    purpose_choices = (
        (FEEDBACK, 'Feedback'),
        (NEW_FEATURE, 'Feature Request'),
        (BUG, 'Bug'),
        (OTHER, 'Other'),
    )

    name = forms.CharField()
    email = forms.EmailField()
    purpose = forms.ChoiceField(choices=purpose_choices)
    message = forms.CharField(widget=forms.Textarea(attrs={'cols': 40, 'rows': 5}))

    def __init__(self, request, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        if request.user.is_authenticated:
            self.fields['name'].required = False
            self.fields['email'].required = False

class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class CreateUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email']
        if not email:
            raise ValidationError("This field is required.")
        if User.objects.filter(email=self.cleaned_data['email']).count():
            raise ValidationError("Email is taken.")
        return self.cleaned_data['email']

    def save(self, request):

        user = super(CreateUserForm, self).save(commit=False)
        user.is_active = False
        user.save()

        context = {
            # 'from_email': settings.DEFAULT_FROM_EMAIL,
            'request': request,
            'protocol': request.scheme,
            'username': self.cleaned_data.get('username'),
            'domain': request.META['HTTP_HOST'],
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
        }

        subject = render_to_string('djangobin/email/activation_subject.txt', context)
        email = render_to_string('djangobin/email/activation_email.txt', context)

        send_mail(subject, email, settings.DEFAULT_FROM_EMAIL, [user.email])

        return user


class SettingForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ('default_language', 'default_expiration', 'default_exposure', 'private')
        widgets = {
            'default_language': forms.Select(attrs={'class': 'selectpicker foo form-control',
                                                    'data-live-search': 'true',
                                                    'data-size': '5'}),
            'default_expiration': forms.Select(attrs={'class': 'selectpicker form-control'}),
            'default_exposure': forms.Select(attrs={'class': 'selectpicker form-control'})

        }


class SearchForm(forms.Form):
    query = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control',
                                                              'placeholder': 'Search'}))
    mysnippet = forms.BooleanField(required=False)



"""
from django import forms
from django.forms import Textarea
from django.core.exceptions import ValidationError
from .models import Language


class LanguageForm(forms.ModelForm):


    name = forms.CharField(max_length=100)
    lang_code = forms.CharField()
    slug = forms.SlugField()
    mime = forms.CharField()
    created_on = forms.DateTimeField()
    updated_on = forms.DateTimeField()
    class Meta:
        model = Language
        fields = '__all__'
        labels = {'mime': 'MIME Type','lang_code': 'Language Code', },
        help_texts = { 'lang_code': 'Short name of the Pygment lexer to use',
                       'file_extension': 'Specify extension like *.txt, *.md etc;'},
        widgets = {'file_extension': Textarea(attrs={'rows': 5, 'cols': 10}), }

    def clean_name(self):
        name = self.cleaned_data['name']
        if name == 'djangobin' or name == 'DJANGOBIN':
            raise ValidationError("name can't be {}.".format(name))
        return name

    def clean_slug(self):
        slug = self.cleaned_data['slug'].lower()
        r = Language.objects.filter(slug=slug)
        if r.count:
            raise ValidationError("{0} already exists".format(slug))

        return slug.lower()

    def clean(self):
        cleaned_data = super(LanguageForm,self).clean()
        slug = cleaned_data.get('slug')
        mime = cleaned_data.get('mime')
        if slug == mime:
            raise ValidationError("Slug and MIME shouldn't be same.")
        return cleaned_data


    def save(self):
        new_lang = Language.objects.create(
            name = self.cleaned_data['name'],
            lang_code = self.cleaned_data['lang_code'],
            slug = self.cleaned_data['slug'],
            mime = self.cleaned_data['mime'],
            created_on = self.cleaned_data['created_on'],
            updated_on = self.cleaned_data['updated_on'],
        )
        return new_lang
"""
