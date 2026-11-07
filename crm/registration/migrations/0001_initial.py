import django.core.validators
import django.db.models.deletion
import registration.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('mobile', models.CharField(max_length=11, unique=True, validators=[django.core.validators.RegexValidator('^01\\d{9}$', 'Mobile must be 11 digits and start with 01.')])),
                ('date_of_birth', models.DateField(blank=True, null=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Bill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bill_id', models.CharField(max_length=20, unique=True, validators=[django.core.validators.RegexValidator('^B-\\d{4,10}$', 'Bill ID must look like B-1001.')])),
                ('products', models.JSONField(default=list)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0)])),
                ('printed_at', models.DateTimeField()),
                ('bill_image', models.ImageField(upload_to=registration.models.bill_image_path)),
                ('ocr_text', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bills', to='registration.registration')),
            ],
            options={
                'ordering': ['-printed_at'],
            },
        ),
    ]
