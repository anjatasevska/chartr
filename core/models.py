from django.db import models


class CoinHistory(models.Model):
    timestamp = models.BigIntegerField(primary_key=True)
    exchange = models.TextField(blank=True, null=True)
    asset_id = models.TextField(blank=True, null=True)
    symbol = models.TextField()
    name = models.TextField(blank=True, null=True)
    pair = models.TextField(blank=True, null=True)
    date = models.TextField(blank=True, null=True)
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    close = models.FloatField()
    volume = models.FloatField()
    scraped_at = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'crypto_ohlcv'
        unique_together = ('timestamp', 'symbol')
        managed = False

    def __str__(self):
        return f"{self.symbol} @ {self.timestamp}"



# Овие две можеш да ги оставиш ако ти требаат за друго
class Coin(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20, unique=True)
    paprika_id = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.name} ({self.symbol})"

class HistoricalPrice(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name="prices")
    timestamp = models.DateTimeField()
    close = models.DecimalField(max_digits=20, decimal_places=8)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.coin.symbol} @ {self.timestamp} = {self.close}"