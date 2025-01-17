from evennia import DefaultCharacter
print("DefaultCharacter:", DefaultCharacter)
from evennia.utils.ansi import ANSIString
from world.wod20th.models import Stat
from evennia.utils import lazy_property
from world.wod20th.models import Note
from world.wod20th.utils.ansi_utils import wrap_ansi
import re
import random

from evennia import DefaultCharacter
print("DefaultCharacter:", DefaultCharacter)

# If DefaultCharacter is None, use object as a fallback
BaseCharacter = DefaultCharacter if DefaultCharacter is not None else object

class Character(BaseCharacter):
    """
    The Character typeclass.
    """

    def at_object_creation(self):
        """
        Called when the character is first created.
        """
        super().at_object_creation()
        self.tags.add("in_material", category="state")
        self.db.unfindable = False  # Add this line
        self.db.fae_desc = ""
        self.db.languages = ["English"]  # Default language
        self.db.speaking_language = None
        self.db.approved = False
        self.db.in_umbra = False  # Use a persistent attribute instead of a tag

    @lazy_property
    def notes(self):
        return Note.objects.filter(character=self)

    def add_note(self, name, text, category="General"):
        return Note.objects.create(
            character=self,
            name=name,
            text=text,
            category=category
        )

    def get_note(self, identifier):
        try:
            return self.notes.get(id=int(identifier))
        except ValueError:
            return self.notes.filter(name__iexact=identifier).first()

    def get_all_notes(self):
        return self.notes.all()

    def update_note(self, identifier, text, category=None):
        note = self.get_note(identifier)
        if note:
            note.text = text
            if category:
                note.category = category
            note.save()
            return True
        return False

    def change_note_status(self, identifier, is_public):
        note = self.get_note(identifier)
        if note:
            note.is_public = is_public
            note.save()
            return True
        return False

    def get_display_name(self, looker, **kwargs):
        """
        Get the name to display for the character.
        """
        name = self.key
        
        if self.db.gradient_name:
            name = ANSIString(self.db.gradient_name)
            if looker.check_permstring("builders"):
                name += f"({self.dbref})"
            return name
        
        # If the looker is builder+ show the dbref
        if looker.check_permstring("builders"):
            name += f"({self.dbref})"

        return name

    def get_languages(self):
        """
        Get the character's known languages.
        """
        return self.db.languages or []  # Return an empty list if None

    def set_speaking_language(self, language):
        """
        Set the character's currently speaking language.
        """
        if language is None:
            self.db.speaking_language = None
        elif language in self.db.languages:
            self.db.speaking_language = language
        else:
            raise ValueError(f"You don't know the language: {language}")

    def get_speaking_language(self):
        """
        Get the character's currently speaking language.
        """
        return self.db.speaking_language

    def detect_tone(self, message):
        """
        Detect the tone of the message based on punctuation and keywords.
        """
        if message.endswith('!'):
            return "excitedly"
        elif message.endswith('?'):
            return "questioningly"
        elif any(word in message.lower() for word in ['hello', 'hi', 'hey', 'greetings']):
            return "in greeting"
        elif any(word in message.lower() for word in ['goodbye', 'bye', 'farewell']):
            return "in farewell"
        elif any(word in message.lower() for word in ['please', 'thank', 'thanks']):
            return "politely"
        elif any(word in message.lower() for word in ['sorry', 'apologize']):
            return "apologetically"
        else:
            return None  # No specific tone detected

    def mask_language(self, message, language):
        """
        Mask the language in the message with more dynamic responses.
        """
        words = len(message.split())
        tone = self.detect_tone(message)

        if words <= 3:
            options = [
                f"<< mutters a few words in {language} >>",
                f"<< something brief in {language} >>",
                f"<< speaks a short {language} phrase >>",
            ]
        elif words <= 10:
            options = [
                f"<< speaks a sentence in {language} >>",
                f"<< a {language} phrase >>",
                f"<< conveys a short message in {language} >>",
            ]
        else:
            options = [
                f"<< gives a lengthy explanation in {language} >>",
                f"<< engages in an extended {language} dialogue >>",
                f"<< speaks at length in {language} >>",
            ]

        masked = random.choice(options)
        
        if tone:
            masked = f"{masked[:-3]}, {tone} >>"

        return masked

    def prepare_say(self, message, language_only=False):
        """
        Prepare the messages for the say command, handling tilde-based language switching.
        """
        use_language = message.lstrip().startswith('~')
        name = self.db.gradient_name if self.db.gradient_name else self.name
        language = self.get_speaking_language()
        
        if use_language:
            # strip the tilde from the message
            message = message[1:].lstrip()
            
                       
            if language and not language_only:
                # Preserve the tilde in the message
                masked_message = self.mask_language(message, language)
                msg_self = f'You say, "{message} |w<< in {language} >>|n"'
                msg_understand = f'{name} says, "{message} |w<< in {language} >>|n"'
                msg_not_understand = f'{name} says, "{masked_message}"'
            else:
                msg_self = f'You say, "{message}"'
                msg_understand = f'{name} says, "{message}"'
                msg_not_understand = msg_understand
               
        else:
            msg_self = f'You say, "{message}"'
            msg_understand = f'{name} says, "{message}"'
            msg_not_understand = msg_understand
           
        
        if language_only and language:
            msg_self = f'{message} |w<< in {language} >>|n'
            msg_understand = f'{message} |w<< in {language} >>|n'
            msg_not_understand = f'{self.mask_language(message, language)}'    
        elif language_only:
            msg_self = f'{message}'
            msg_understand = f'{message}'
            msg_not_understand = f'{message}'
            language = None

        else:
            language = None

        return msg_self, msg_understand, msg_not_understand, language

    def step_sideways(self):
        """Attempt to step sideways into the Umbra."""
        if self.db.in_umbra:
            self.msg("You are already in the Umbra.")
            return False
        
        if self.location:
            success = self.location.step_sideways(self)
            if success:
                self.db.in_umbra = True
                self.msg("You have stepped sideways into the Umbra.")
                self.location.msg_contents(f"{self.name} shimmers and fades from view as they step into the Umbra.", exclude=[self], from_obj=self)
            return success
        else:
            self.msg("You can't step sideways here.")
            return False

    def return_from_umbra(self):
        """Return from the Umbra to the material world."""
        if not self.db.in_umbra:
            self.msg("You are not in the Umbra.")
            return False
        
        self.db.in_umbra = False
        self.msg("You step back into the material world.")
        self.location.msg_contents(f"{self.name} shimmers into view as they return from the Umbra.", exclude=[self], from_obj=self)
        return True

    def return_appearance(self, looker, **kwargs):
        """
        This formats a description for any object looking at this object.
        """
        if not looker:
            return ""
        
        # Get the description
        desc = self.db.desc

        # Start with the name
        string = f"|c{self.get_display_name(looker)}|n\n"

        # Process character description
        if desc:
            # Replace both %t and |- with a consistent tab marker
            desc = desc.replace('%t', '|t').replace('|-', '|t')
            
            paragraphs = desc.split('%r')
            formatted_paragraphs = []
            for p in paragraphs:
                if not p.strip():
                    formatted_paragraphs.append('')  # Add blank line for empty paragraph
                    continue
                
                # Handle tabs manually
                lines = p.split('|t')
                indented_lines = [line.strip() for line in lines]
                indented_text = '\n    '.join(indented_lines)
                
                # Wrap each line individually
                wrapped_lines = [wrap_ansi(line, width=78) for line in indented_text.split('\n')]
                formatted_paragraphs.append('\n'.join(wrapped_lines))
            
            # Join paragraphs with a single newline, and remove any consecutive newlines
            joined_paragraphs = '\n'.join(formatted_paragraphs)
            joined_paragraphs = re.sub(r'\n{3,}', '\n\n', joined_paragraphs)
            
            string += joined_paragraphs + "\n"

        # Add any other details you want to include in the character's appearance
        # For example, you might want to add information about their equipment, stats, etc.

        return string

    def announce_move_from(self, destination, msg=None, mapping=None, **kwargs):
        """
        Called just before moving out of the current room.
        """
        if not self.location:
            return

        string = f"{self.name} is leaving {self.location}, heading for {destination}."
        
        # Send message directly to the room
        self.location.msg_contents(string, exclude=[self], from_obj=self)

    def announce_move_to(self, source_location, msg=None, mapping=None, **kwargs):
        """
        Called just after arriving in a new room.
        """
        if not source_location:
            return

        string = f"{self.name} arrives to {self.location} from {source_location}."
        
        # Send message directly to the room
        self.location.msg_contents(string, exclude=[self], from_obj=self)

    def at_say(self, message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs):
        """Hook method for the say command."""
        if not self.location:
            return

        # Filter receivers based on Umbra state
        filtered_receivers = [
            r for r in self.location.contents 
            if hasattr(r, 'has_account') and r.has_account and r.db.in_umbra == self.db.in_umbra
        ]

        # Prepare the say messages
        msg_self, msg_understand, msg_not_understand, language = self.prepare_say(message)

        # Send messages to receivers
        for receiver in filtered_receivers:
            if receiver != self:
                if language and language in receiver.get_languages():
                    receiver.msg(msg_understand)
                else:
                    receiver.msg(msg_not_understand)

        # Send message to the speaker
        self.msg(msg_self)

    def at_pose(self, pose_understand, pose_not_understand, pose_self, speaking_language):
        if not self.location:
            return

        # Filter receivers based on Umbra state
        filtered_receivers = [
            r for r in self.location.contents 
            if hasattr(r, 'has_account') and r.has_account and r.db.in_umbra == self.db.in_umbra
        ]

        # Send messages to receivers
        for receiver in filtered_receivers:
            if receiver != self:
                if speaking_language and speaking_language in receiver.get_languages():
                    receiver.msg(pose_understand)
                else:
                    receiver.msg(pose_not_understand)

        # Send message to the poser
        self.msg(pose_self)

        # Log the pose (only visible to those in the same realm)
        self.location.msg_contents(pose_understand, exclude=filtered_receivers + [self], from_obj=self)

    def at_emote(self, message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs):
        """Display an emote to the room."""
        if not self.location:
            return

        # Filter receivers based on Umbra state
        filtered_receivers = [
            r for r in self.location.contents 
            if hasattr(r, 'has_account') and r.has_account and r.db.in_umbra == self.db.in_umbra
        ]
        
        # Send the emote to filtered receivers
        for receiver in filtered_receivers:
            if receiver != self:
                receiver.msg(message)
        
        # Send the emote to the emitter
        self.msg(msg_self or message)

    def get_stat(self, category, stat_type, stat_name, temp=False):
        """
        Retrieve the value of a stat, considering instances if applicable.
        """
        if not hasattr(self.db, "stats") or not self.db.stats:
            self.db.stats = {}

        category_stats = self.db.stats.get(category, {})
        type_stats = category_stats.get(stat_type, {})

        # Check for the stat in the current category and type
        if stat_name in type_stats:
            return type_stats[stat_name]['temp' if temp else 'perm']

        # If not found and the category is 'pools', check in 'dual' as well
        if category == 'pools' and 'dual' in self.db.stats:
            dual_stats = self.db.stats['dual']
            if stat_name in dual_stats:
                return dual_stats[stat_name]['temp' if temp else 'perm']

        # If still not found, check the Stat model
        stat = Stat.objects.filter(name=stat_name, category=category, stat_type=stat_type).first()
        if stat:
            return stat.default

        return None

    def set_stat(self, category, stat_type, stat_name, value, temp=False):
        """
        Set the value of a stat, considering instances if applicable.
        """
        if not hasattr(self.db, "stats") or not self.db.stats:
            self.db.stats = {}
        if category not in self.db.stats:
            self.db.stats[category] = {}
        if stat_type not in self.db.stats[category]:
            self.db.stats[category][stat_type] = {}
        if stat_name not in self.db.stats[category][stat_type]:
            self.db.stats[category][stat_type][stat_name] = {'perm': 0, 'temp': 0}
        if temp:
            self.db.stats[category][stat_type][stat_name]['temp'] = value
        else:
            self.db.stats[category][stat_type][stat_name]['perm'] = value
            
    def check_stat_value(self, category, stat_type, stat_name, value, temp=False):
        """
        Check if a value is valid for a stat, considering instances if applicable.
        """
        from world.wod20th.models import Stat  
        stat = Stat.objects.filter(name=stat_name, category=category, stat_type=stat_type).first()
        if stat:
            stat_values = stat.values
            return value in stat_values['temp'] if temp else value in stat_values['perm']
        return False

    def colorize_name(self, message):
        """
        Replace instances of the character's name with their gradient name in the message.
        """
        if self.db.gradient_name:
            gradient_name = ANSIString(self.db.gradient_name)
            return message.replace(self.name, str(gradient_name))
        return message
 
    def delete_note(self, name):
        if self.character_sheet:
            return self.character_sheet.delete_note(name)
        return False

    def get_notes_by_category(self, category):
        if self.character_sheet:
            return self.character_sheet.get_notes_by_category(category)
        return []

    def approve_note(self, name):
        if self.character_sheet:
            return self.character_sheet.approve_note(name)
        return False

    def unapprove_note(self, name):
        if self.character_sheet:
            return self.character_sheet.unapprove_note(name)
        return False

    def change_note_status(self, name, is_public):
        if self.character_sheet:
            return self.character_sheet.change_note_status(name, is_public)
        return False

    def get_fae_description(self):
        """Get the fae description of the character."""
        return self.db.fae_desc or f"{self.name} has no visible fae aspect."

    def set_fae_description(self, description):
        """Set the fae description of the character."""
        self.db.fae_desc = description

    def is_fae_perceiver(self):
        """Check if the character is a Changeling or Kinain."""
        if not self.db.stats or 'other' not in self.db.stats or 'splat' not in self.db.stats['other']:
            return False
        splat = self.db.stats['other']['splat'].get('Splat', {}).get('perm', '')
        return splat in ['Changeling', 'Kinain']